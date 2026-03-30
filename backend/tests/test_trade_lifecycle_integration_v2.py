import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.core.security import get_current_user
from backend.database import get_db
from backend.main import app


@pytest.fixture
def api_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_dependencies(api_db):
    def override_get_db():
        try:
            yield api_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def _seed_league(api_db, *, with_past_deadline: bool = False, name: str = "Trade Lifecycle API League"):
    league = models.League(name=name, current_season=2026)
    api_db.add(league)
    api_db.commit()
    api_db.refresh(league)
    suffix = str(league.id)

    deadline = "2000-01-01T00:00:00Z" if with_past_deadline else None
    api_db.add(models.LeagueSettings(league_id=league.id, roster_size=16, trade_deadline=deadline))

    team_a = models.User(
        username=f"api-team-a-{suffix}",
        hashed_password="pw",
        league_id=league.id,
        future_draft_budget=30,
    )
    team_b = models.User(
        username=f"api-team-b-{suffix}",
        hashed_password="pw",
        league_id=league.id,
        future_draft_budget=20,
    )
    commissioner = models.User(
        username=f"api-comm-{suffix}",
        hashed_password="pw",
        league_id=league.id,
        is_commissioner=True,
        future_draft_budget=0,
    )
    api_db.add_all([team_a, team_b, commissioner])
    api_db.commit()
    api_db.refresh(team_a)
    api_db.refresh(team_b)
    api_db.refresh(commissioner)

    player_a = models.Player(name="API A", position="RB", nfl_team="AAA")
    player_b = models.Player(name="API B", position="WR", nfl_team="BBB")
    api_db.add_all([player_a, player_b])
    api_db.commit()
    api_db.refresh(player_a)
    api_db.refresh(player_b)

    pick_a_player = models.DraftPick(league_id=league.id, owner_id=team_a.id, player_id=player_a.id, year=2027)
    pick_b_player = models.DraftPick(league_id=league.id, owner_id=team_b.id, player_id=player_b.id, year=2027)
    pick_a_extra = models.DraftPick(league_id=league.id, owner_id=team_a.id, player_id=None, year=2028)
    pick_b_extra = models.DraftPick(league_id=league.id, owner_id=team_b.id, player_id=None, year=2028)
    api_db.add_all([pick_a_player, pick_b_player, pick_a_extra, pick_b_extra])
    api_db.commit()
    api_db.refresh(pick_a_extra)
    api_db.refresh(pick_b_extra)

    return {
        "league": league,
        "team_a": team_a,
        "team_b": team_b,
        "commissioner": commissioner,
        "player_a": player_a,
        "player_b": player_b,
        "pick_a_extra": pick_a_extra,
        "pick_b_extra": pick_b_extra,
    }


def test_trade_lifecycle_submit_pending_approve_and_history(client, api_db):
    seeded = _seed_league(api_db, name="Trade Lifecycle API League A")

    app.dependency_overrides[get_current_user] = lambda: seeded["team_a"]
    submit_response = client.post(
        f"/trades/leagues/{seeded['league'].id}/submit-v2",
        json={
            "team_a_id": seeded["team_a"].id,
            "team_b_id": seeded["team_b"].id,
            "assets_from_a": [
                {"asset_type": "PLAYER", "player_id": seeded["player_a"].id},
                {"asset_type": "DRAFT_PICK", "draft_pick_id": seeded["pick_a_extra"].id, "season_year": 2028},
                {"asset_type": "DRAFT_DOLLARS", "amount": 5},
            ],
            "assets_from_b": [
                {"asset_type": "PLAYER", "player_id": seeded["player_b"].id},
                {"asset_type": "DRAFT_DOLLARS", "amount": 2},
            ],
        },
    )
    assert submit_response.status_code == 200
    trade_id = submit_response.json()["trade_id"]

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    pending_response = client.get(f"/trades/leagues/{seeded['league'].id}/pending-v2")
    assert pending_response.status_code == 200
    pending_rows = pending_response.json()
    assert any(row["id"] == trade_id and row["status"] == "PENDING" for row in pending_rows)

    approve_response = client.post(
        f"/trades/leagues/{seeded['league'].id}/{trade_id}/approve-v2",
        json={"commissioner_comments": "Approved in integration test"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["trade"]["status"] == "APPROVED"

    history_response = client.get(f"/trades/leagues/{seeded['league'].id}/{trade_id}/history-v2")
    assert history_response.status_code == 200
    history = history_response.json()
    assert [row["event_type"] for row in history] == ["SUBMITTED", "APPROVED"]

    updated_team_a = api_db.get(models.User, seeded["team_a"].id)
    updated_team_b = api_db.get(models.User, seeded["team_b"].id)
    assert updated_team_a.future_draft_budget == 27
    assert updated_team_b.future_draft_budget == 23


def test_trade_lifecycle_reject_records_reason_and_history(client, api_db):
    seeded = _seed_league(api_db, name="Trade Lifecycle API League B")

    app.dependency_overrides[get_current_user] = lambda: seeded["team_a"]
    submit_response = client.post(
        f"/trades/leagues/{seeded['league'].id}/submit-v2",
        json={
            "team_a_id": seeded["team_a"].id,
            "team_b_id": seeded["team_b"].id,
            "assets_from_a": [{"asset_type": "PLAYER", "player_id": seeded["player_a"].id}],
            "assets_from_b": [{"asset_type": "PLAYER", "player_id": seeded["player_b"].id}],
        },
    )
    assert submit_response.status_code == 200
    trade_id = submit_response.json()["trade_id"]

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    reject_response = client.post(
        f"/trades/leagues/{seeded['league'].id}/{trade_id}/reject-v2",
        json={"commissioner_comments": "Roster impact too high"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["trade"]["status"] == "REJECTED"

    history_response = client.get(f"/trades/leagues/{seeded['league'].id}/{trade_id}/history-v2")
    assert history_response.status_code == 200
    history = history_response.json()
    assert [row["event_type"] for row in history] == ["SUBMITTED", "REJECTED"]
    assert history[-1]["comment"] == "Roster impact too high"


def test_trade_lifecycle_rejects_invalid_assets_and_closed_window(client, api_db):
    seeded = _seed_league(api_db, name="Trade Lifecycle API League C")

    app.dependency_overrides[get_current_user] = lambda: seeded["team_a"]
    invalid_asset_response = client.post(
        f"/trades/leagues/{seeded['league'].id}/submit-v2",
        json={
            "team_a_id": seeded["team_a"].id,
            "team_b_id": seeded["team_b"].id,
            "assets_from_a": [
                {
                    "asset_type": "DRAFT_PICK",
                    # Team A trying to offer Team B's pick should fail validation.
                    "draft_pick_id": seeded["pick_b_extra"].id,
                    "season_year": 2028,
                }
            ],
            "assets_from_b": [{"asset_type": "PLAYER", "player_id": seeded["player_b"].id}],
        },
    )
    assert invalid_asset_response.status_code == 400

    closed_seeded = _seed_league(api_db, with_past_deadline=True, name="Trade Lifecycle API League D")
    app.dependency_overrides[get_current_user] = lambda: closed_seeded["team_a"]
    closed_window_response = client.post(
        f"/trades/leagues/{closed_seeded['league'].id}/submit-v2",
        json={
            "team_a_id": closed_seeded["team_a"].id,
            "team_b_id": closed_seeded["team_b"].id,
            "assets_from_a": [{"asset_type": "PLAYER", "player_id": closed_seeded["player_a"].id}],
            "assets_from_b": [{"asset_type": "PLAYER", "player_id": closed_seeded["player_b"].id}],
        },
    )
    assert closed_window_response.status_code == 400
    assert "Trade proposals are closed" in str(closed_window_response.json().get("detail"))
