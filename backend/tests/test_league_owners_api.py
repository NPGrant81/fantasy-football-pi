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


def test_get_league_owners_contract_and_league_scoped_stats(client, api_db):
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


def test_get_league_owners_ignores_legacy_null_league_matchups(client, api_db):
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

    response = client.get(f"/leagues/owners?league_id={league.id}")
    assert response.status_code == 200
    payload = response.json()
    owner_a_row = next(row for row in payload if row["id"] == owner_a.id)

    assert owner_a_row["wins"] == 0
    assert owner_a_row["losses"] == 0
    assert owner_a_row["pf"] == 0.0
    assert owner_a_row["pa"] == 0.0
