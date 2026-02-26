import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.league import get_league_budgets, get_league_settings


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_league(db):
    l = models.League(name="L")
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def make_user(db, league, username="u", team="t"):
    u = models.User(username=username, hashed_password="pw", league_id=league.id, team_name=team)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_get_league_budgets_empty(db_session):
    league = make_league(db_session)
    # no budgets exist yet
    u1 = make_user(db_session, league, "a", "TeamA")
    u2 = make_user(db_session, league, "b", "TeamB")

    result = get_league_budgets(league_id=league.id, year=2026, db=db_session)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["team_name"] in ("TeamA", "TeamB")
    assert result[0]["total_budget"] is None


def test_get_league_budgets_with_data(db_session):
    league = make_league(db_session)
    u1 = make_user(db_session, league, "a", "TeamA")
    u2 = make_user(db_session, league, "b", "TeamB")
    # insert budgets
    db_session.add(models.DraftBudget(league_id=league.id, owner_id=u1.id, year=2026, total_budget=150))
    db_session.add(models.DraftBudget(league_id=league.id, owner_id=u2.id, year=2026, total_budget=175))
    db_session.commit()

    result = get_league_budgets(league_id=league.id, year=2026, db=db_session)
    assert len(result) == 2
    # budgets should be filled
    budgets = {r["owner_id"]: r["total_budget"] for r in result}
    assert budgets[u1.id] == 150
    assert budgets[u2.id] == 175


def test_get_league_settings_defaults(db_session):
    league = make_league(db_session)
    # no settings row initially
    assert db_session.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league.id).first() is None

    cfg = get_league_settings(league_id=league.id, db=db_session)
    # should return the hard-coded defaults from the router
    assert cfg.roster_size == 14
    assert cfg.salary_cap == 200
    assert isinstance(cfg.starting_slots, dict)
    assert cfg.starting_slots.get("QB") == 1

    # the defaults should also now be persisted to the database
    settings = db_session.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league.id).first()
    assert settings is not None
    assert settings.roster_size == 14


def test_get_league_settings_existing(db_session):
    league = make_league(db_session)
    # create a custom settings record to ensure the router returns it unchanged
    custom = models.LeagueSettings(
        league_id=league.id,
        roster_size=22,
        salary_cap=500,
        starting_slots={"QB": 2},
    )
    db_session.add(custom)
    db_session.commit()

    cfg = get_league_settings(league_id=league.id, db=db_session)
    assert cfg.roster_size == 22
    assert cfg.salary_cap == 500
    assert cfg.starting_slots.get("QB") == 2
