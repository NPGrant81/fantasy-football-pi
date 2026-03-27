import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.core import security
from backend.database import get_db
from backend.main import app


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


def _login(client, username: str, password: str):
    response = client.post(
        "/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    return response


def test_get_league_owners_contract_and_league_scoped_stats(client, api_db, monkeypatch):
    monkeypatch.setattr(security, 'verify_password', lambda plain, hashed: plain == "secret" and hashed == "h")

    league_one = models.League(name="L1")
    league_two = models.League(name="L2")
    api_db.add_all([league_one, league_two])
    api_db.commit()
    api_db.refresh(league_one)
    api_db.refresh(league_two)

    owner_a = models.User(username="owner-a", email=None, hashed_password="h", league_id=league_one.id)
    owner_b = models.User(username="owner-b", email=None, hashed_password="h", league_id=league_one.id)
    outsider = models.User(username="outsider", email=None, hashed_password="h", league_id=league_two.id)
    api_db.add_all([owner_a, owner_b, outsider])
    api_db.commit()
    api_db.refresh(owner_a)
    api_db.refresh(owner_b)
    api_db.refresh(outsider)

    # In-league completed matchup: owner_a beats owner_b.
    matchup_l1 = models.Matchup(
        week=1,
        home_team_id=owner_a.id,
        away_team_id=owner_b.id,
        home_score=111.5,
        away_score=108.0,
        is_completed=True,
        league_id=league_one.id,
    )
    # Different league matchup includes owner_a and must be ignored.
    matchup_l2 = models.Matchup(
        week=1,
        home_team_id=owner_a.id,
        away_team_id=outsider.id,
        home_score=300.0,
        away_score=1.0,
        is_completed=True,
        league_id=league_two.id,
    )
    api_db.add_all([matchup_l1, matchup_l2])
    api_db.commit()

    _login(client, "owner-a", "secret")
    response = client.get(f"/leagues/owners?league_id={league_one.id}")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)

    owner_a_row = next(row for row in payload if row["id"] == owner_a.id)

    # Contract fields consumed by Home standings table.
    for field in ["wins", "losses", "ties", "pf", "pa", "points_for", "points_against", "win_pct"]:
        assert field in owner_a_row

    # Stats should include only league_one data.
    assert owner_a_row["wins"] == 1
    assert owner_a_row["losses"] == 0
    assert owner_a_row["ties"] == 0
    assert owner_a_row["pf"] == 111.5
    assert owner_a_row["pa"] == 108.0
    assert owner_a_row["points_for"] == 111.5
    assert owner_a_row["points_against"] == 108.0


def test_get_league_owners_ignores_legacy_null_league_matchups(client, api_db, monkeypatch):
    monkeypatch.setattr(security, 'verify_password', lambda plain, hashed: plain == "secret" and hashed == "h")

    league = models.League(name="L3")
    api_db.add(league)
    api_db.commit()
    api_db.refresh(league)

    owner_a = models.User(username="owner-null-a", email=None, hashed_password="h", league_id=league.id)
    owner_b = models.User(username="owner-null-b", email=None, hashed_password="h", league_id=league.id)
    api_db.add_all([owner_a, owner_b])
    api_db.commit()
    api_db.refresh(owner_a)
    api_db.refresh(owner_b)

    api_db.add(
        models.Matchup(
            week=2,
            home_team_id=owner_a.id,
            away_team_id=owner_b.id,
            home_score=400.0,
            away_score=1.0,
            is_completed=True,
            league_id=None,
        )
    )
    api_db.commit()

    _login(client, "owner-null-a", "secret")
    response = client.get(f"/leagues/owners?league_id={league.id}")
    assert response.status_code == 200
    payload = response.json()
    owner_a_row = next(row for row in payload if row["id"] == owner_a.id)

    assert owner_a_row["wins"] == 0
    assert owner_a_row["losses"] == 0
    assert owner_a_row["pf"] == 0.0
    assert owner_a_row["pa"] == 0.0


def test_get_league_owners_default_order_applies_record_tiebreak_chain(client, api_db, monkeypatch):
    monkeypatch.setattr(security, 'verify_password', lambda plain, hashed: plain == "secret" and hashed == "h")

    league = models.League(name="Standings Sort League")
    api_db.add(league)
    api_db.commit()
    api_db.refresh(league)

    alpha = models.User(username="alpha", email=None, hashed_password="h", league_id=league.id)
    bravo = models.User(username="bravo", email=None, hashed_password="h", league_id=league.id)
    api_db.add_all([alpha, bravo])
    api_db.commit()
    api_db.refresh(alpha)
    api_db.refresh(bravo)

    # Same wins/losses/ties for both owners. Alpha should rank above Bravo via PF.
    api_db.add_all(
        [
            models.Matchup(
                week=1,
                home_team_id=alpha.id,
                away_team_id=bravo.id,
                home_score=110.0,
                away_score=90.0,
                is_completed=True,
                league_id=league.id,
            ),
            models.Matchup(
                week=2,
                home_team_id=alpha.id,
                away_team_id=bravo.id,
                home_score=85.0,
                away_score=100.0,
                is_completed=True,
                league_id=league.id,
            ),
            models.Matchup(
                week=3,
                home_team_id=alpha.id,
                away_team_id=bravo.id,
                home_score=95.0,
                away_score=95.0,
                is_completed=True,
                league_id=league.id,
            ),
        ]
    )
    api_db.commit()

    _login(client, "alpha", "secret")
    response = client.get(f"/leagues/owners?league_id={league.id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload[0]["id"] == alpha.id
    assert payload[1]["id"] == bravo.id
    assert payload[0]["wins"] == payload[1]["wins"] == 1
    assert payload[0]["losses"] == payload[1]["losses"] == 1
    assert payload[0]["ties"] == payload[1]["ties"] == 1
    assert payload[0]["pf"] > payload[1]["pf"]


def test_get_league_owners_grouped_order_sorts_within_division(client, api_db, monkeypatch):
    monkeypatch.setattr(security, 'verify_password', lambda plain, hashed: plain == "secret" and hashed == "h")

    league = models.League(name="Division Sort League")
    api_db.add(league)
    api_db.commit()
    api_db.refresh(league)

    east = models.Division(league_id=league.id, name="East", order_index=1)
    west = models.Division(league_id=league.id, name="West", order_index=2)
    api_db.add_all([east, west])
    api_db.commit()
    api_db.refresh(east)
    api_db.refresh(west)

    east_top = models.User(
        username="east-top",
        email=None,
        hashed_password="h",
        league_id=league.id,
        division_id=east.id,
    )
    east_low = models.User(
        username="east-low",
        email=None,
        hashed_password="h",
        league_id=league.id,
        division_id=east.id,
    )
    west_only = models.User(
        username="west-only",
        email=None,
        hashed_password="h",
        league_id=league.id,
        division_id=west.id,
    )
    api_db.add_all([east_top, east_low, west_only])
    api_db.commit()
    api_db.refresh(east_top)
    api_db.refresh(east_low)
    api_db.refresh(west_only)

    api_db.add_all(
        [
            models.Matchup(
                week=1,
                home_team_id=east_top.id,
                away_team_id=east_low.id,
                home_score=120.0,
                away_score=100.0,
                is_completed=True,
                league_id=league.id,
            ),
            models.Matchup(
                week=2,
                home_team_id=east_low.id,
                away_team_id=east_top.id,
                home_score=98.0,
                away_score=110.0,
                is_completed=True,
                league_id=league.id,
            ),
            models.Matchup(
                week=3,
                home_team_id=west_only.id,
                away_team_id=east_low.id,
                home_score=130.0,
                away_score=90.0,
                is_completed=True,
                league_id=league.id,
            ),
        ]
    )
    api_db.commit()

    _login(client, "east-top", "secret")
    response = client.get(f"/leagues/owners?league_id={league.id}&group_by_division=true")
    assert response.status_code == 200
    payload = response.json()

    # Division grouping keeps East owners ahead of West owners, while sorting East internally.
    assert payload[0]["division_id"] == east.id
    assert payload[1]["division_id"] == east.id
    assert payload[2]["division_id"] == west.id
    assert payload[0]["id"] == east_top.id


def test_get_league_owners_returns_403_for_league_mapping_mismatch(client, api_db, monkeypatch):
    monkeypatch.setattr(security, 'verify_password', lambda plain, hashed: plain == "secret" and hashed == "h")

    league_one = models.League(name="Mismatch One")
    league_two = models.League(name="Mismatch Two")
    api_db.add_all([league_one, league_two])
    api_db.commit()
    api_db.refresh(league_one)
    api_db.refresh(league_two)

    user = models.User(username="mapped-user", email=None, hashed_password="h", league_id=league_one.id)
    api_db.add(user)
    api_db.commit()

    _login(client, "mapped-user", "secret")
    response = client.get(f"/leagues/owners?league_id={league_two.id}")

    assert response.status_code == 403
    detail = response.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error_code") == "LEAGUE_MAPPING_MISMATCH"
    assert detail.get("user_league_id") == league_one.id
    assert detail.get("requested_league_id") == league_two.id
