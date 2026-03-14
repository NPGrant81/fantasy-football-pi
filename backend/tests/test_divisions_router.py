import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.database import get_db
from backend.main import app
from backend.routers import divisions as divisions_router


@pytest.fixture
def api_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db, TestingSessionLocal
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_db(api_db):
    db, _ = api_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def _seed_league(db, team_count: int = 9):
    league = models.League(name=f"DivisionLeague-{team_count}")
    db.add(league)
    db.commit()
    db.refresh(league)

    commissioner = models.User(
        username="commish-div",
        email="commish@example.com",
        hashed_password="h",
        league_id=league.id,
        is_commissioner=True,
    )
    db.add(commissioner)
    db.flush()

    users = [commissioner]
    for idx in range(team_count - 1):
        user = models.User(
            username=f"owner-{idx}",
            email=f"owner-{idx}@example.com",
            hashed_password="h",
            league_id=league.id,
        )
        db.add(user)
        users.append(user)

    db.commit()
    return league, commissioner, users


def test_upsert_config_allows_odd_division_count_if_evenly_divisible(client, api_db):
    db, _ = api_db
    league, commissioner, _ = _seed_league(db, team_count=9)

    app.dependency_overrides[divisions_router.get_current_user] = lambda: commissioner
    payload = {
        "season": 2026,
        "enabled": True,
        "division_count": 3,
        "assignment_method": "heuristic",
        "names": [
            {"name": "North", "order_index": 0},
            {"name": "South", "order_index": 1},
            {"name": "West", "order_index": 2},
        ],
    }

    res = client.put(f"/leagues/{league.id}/divisions/config", json=payload)
    assert res.status_code == 200

    get_res = client.get(f"/leagues/{league.id}/divisions/config?season=2026")
    assert get_res.status_code == 200
    body = get_res.json()
    assert body["division_count"] == 3
    assert len(body["divisions"]) == 3


def test_preview_and_finalize_heuristic_assignment(client, api_db):
    db, _ = api_db
    league, commissioner, users = _seed_league(db, team_count=9)
    app.dependency_overrides[divisions_router.get_current_user] = lambda: commissioner

    config_payload = {
        "season": 2026,
        "enabled": True,
        "division_count": 3,
        "assignment_method": "heuristic",
        "random_seed": "seed-div-2026",
        "names": [
            {"name": "Alpha", "order_index": 0},
            {"name": "Beta", "order_index": 1},
            {"name": "Gamma", "order_index": 2},
        ],
    }
    cfg = client.put(f"/leagues/{league.id}/divisions/config", json=config_payload)
    assert cfg.status_code == 200

    preview_res = client.post(
        f"/leagues/{league.id}/divisions/assignment-preview",
        json={"season": 2026, "assignment_method": "heuristic", "random_seed": "seed-div-2026"},
    )
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert "confidence_score" in preview
    assert "imbalance_pct" in preview
    assert len(preview["assignments"]) == 3

    finalize_res = client.post(
        f"/leagues/{league.id}/divisions/finalize",
        json={"season": 2026, "assignment_method": "heuristic", "random_seed": "seed-div-2026"},
    )
    assert finalize_res.status_code == 200

    db.refresh(commissioner)
    assert commissioner.division_id is not None


def test_upsert_config_clears_user_divisions_after_finalize(client, api_db):
    db, _ = api_db
    league, commissioner, users = _seed_league(db, team_count=9)
    app.dependency_overrides[divisions_router.get_current_user] = lambda: commissioner

    initial_payload = {
        "season": 2026,
        "enabled": True,
        "division_count": 3,
        "assignment_method": "heuristic",
        "random_seed": "seed-div-2026",
        "names": [
            {"name": "Alpha", "order_index": 0},
            {"name": "Beta", "order_index": 1},
            {"name": "Gamma", "order_index": 2},
        ],
    }
    cfg = client.put(f"/leagues/{league.id}/divisions/config", json=initial_payload)
    assert cfg.status_code == 200

    finalize_res = client.post(
        f"/leagues/{league.id}/divisions/finalize",
        json={"season": 2026, "assignment_method": "heuristic", "random_seed": "seed-div-2026"},
    )
    assert finalize_res.status_code == 200

    assigned_owner = users[1]
    db.refresh(assigned_owner)
    assert assigned_owner.division_id is not None
    old_division_id = assigned_owner.division_id

    reconfig_payload = {
        "season": 2026,
        "enabled": True,
        "division_count": 3,
        "assignment_method": "random",
        "random_seed": "seed-div-2026-b",
        "names": [
            {"name": "North", "order_index": 0},
            {"name": "South", "order_index": 1},
            {"name": "West", "order_index": 2},
        ],
    }
    reconfig = client.put(f"/leagues/{league.id}/divisions/config", json=reconfig_payload)
    assert reconfig.status_code == 200

    db.refresh(assigned_owner)
    assert assigned_owner.division_id is None
    assert assigned_owner.division_obj is None
    refreshed_divisions = db.query(models.Division).filter(
        models.Division.league_id == league.id,
        models.Division.season == 2026,
    ).all()
    assert len(refreshed_divisions) == 3
    assert {division.name for division in refreshed_divisions} == {"North", "South", "West"}


def test_report_name_creates_db_queue_entry(client, api_db):
    db, _ = api_db
    league, commissioner, _ = _seed_league(db, team_count=9)
    app.dependency_overrides[divisions_router.get_current_user] = lambda: commissioner

    # Seed a division so name validation has something to check against
    division = models.Division(league_id=league.id, season=2026, name="Bad Name", order_index=0)
    db.add(division)
    db.commit()

    res = client.post(
        f"/leagues/{league.id}/divisions/report-name",
        json={"season": 2026, "division_name": "Bad Name", "reason": "inappropriate"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "queued"

    report = db.query(models.DivisionNameReport).filter(models.DivisionNameReport.id == body["report_id"]).first()
    assert report is not None
    assert report.status == "open"


def test_report_name_rejects_cross_league_user(client, api_db):
    db, _ = api_db
    league, _, _ = _seed_league(db, team_count=4)

    other_league = models.League(name="OtherLeague")
    db.add(other_league)
    db.commit()
    db.refresh(other_league)
    outsider = models.User(
        username="outsider",
        email="outsider@example.com",
        hashed_password="h",
        league_id=other_league.id,
    )
    db.add(outsider)
    db.commit()

    app.dependency_overrides[divisions_router.get_current_user] = lambda: outsider
    res = client.post(
        f"/leagues/{league.id}/divisions/report-name",
        json={"division_name": "North", "reason": "bad"},
    )
    assert res.status_code == 403


def test_report_name_superuser_can_report_any_league(client, api_db):
    db, _ = api_db
    league, _, _ = _seed_league(db, team_count=4)

    superuser = models.User(
        username="superadmin",
        email="superadmin@example.com",
        hashed_password="h",
        is_superuser=True,
    )
    db.add(superuser)
    db.commit()

    app.dependency_overrides[divisions_router.get_current_user] = lambda: superuser
    res = client.post(
        f"/leagues/{league.id}/divisions/report-name",
        json={"division_name": "AnyName", "reason": "check"},
    )
    assert res.status_code == 200


def test_report_name_rejects_nonexistent_division_name(client, api_db):
    db, _ = api_db
    league, commissioner, _ = _seed_league(db, team_count=4)

    division = models.Division(league_id=league.id, season=2026, name="North", order_index=0)
    db.add(division)
    db.commit()

    app.dependency_overrides[divisions_router.get_current_user] = lambda: commissioner
    res = client.post(
        f"/leagues/{league.id}/divisions/report-name",
        json={"season": 2026, "division_name": "DoesNotExist", "reason": "bad"},
    )
    assert res.status_code == 422


def test_report_name_skips_name_validation_when_no_season(client, api_db):
    db, _ = api_db
    league, commissioner, _ = _seed_league(db, team_count=4)

    app.dependency_overrides[divisions_router.get_current_user] = lambda: commissioner
    res = client.post(
        f"/leagues/{league.id}/divisions/report-name",
        json={"division_name": "Whatever"},
    )
    assert res.status_code == 200
