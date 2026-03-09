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


def test_get_league_owners_contract_and_scoping(client, api_db):
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

    # In-scope matchup for league_one.
    in_scope = models.Matchup(
        week=1,
        home_team_id=owner_a.id,
        away_team_id=owner_b.id,
        home_score=111.5,
        away_score=108.0,
        is_completed=True,
        league_id=league_one.id,
    )
    # Out-of-scope matchup that should not affect league_one standings.
    out_of_scope = models.Matchup(
        week=1,
        home_team_id=owner_a.id,
        away_team_id=outsider.id,
        home_score=300.0,
        away_score=1.0,
        is_completed=True,
        league_id=league_two.id,
    )
    api_db.add_all([in_scope, out_of_scope])
    api_db.commit()

    response = client.get(f"/leagues/owners?league_id={league_one.id}")

    assert response.status_code == 200
    payload = response.json()
    owner_row = next(row for row in payload if row["id"] == owner_a.id)

    for field in [
        "wins",
        "losses",
        "ties",
        "pf",
        "pa",
        "points_for",
        "points_against",
        "win_pct",
    ]:
        assert field in owner_row

    assert owner_row["wins"] == 1
    assert owner_row["losses"] == 0
    assert owner_row["ties"] == 0
    assert owner_row["pf"] == 111.5
    assert owner_row["pa"] == 108.0
    assert owner_row["points_for"] == 111.5
    assert owner_row["points_against"] == 108.0
