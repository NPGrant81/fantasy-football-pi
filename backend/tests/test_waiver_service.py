import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.services.player_service import get_league_free_agents, search_all_players
from backend.services.waiver_service import process_claim


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
    league = models.League(name="Waiver League")
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def make_user(db, league, username="owner"):
    user = models.User(username=username, hashed_password="pw", league_id=league.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_player(db, name):
    player = models.Player(name=name, position="RB", nfl_team="ABC")
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def test_process_claim_writes_faab_ledger_entry(db_session):
    league = make_league(db_session)
    user = make_user(db_session, league, "waiver-owner-1")
    target = make_player(db_session, "Target")

    pick = process_claim(db_session, user=user, player_id=target.id, bid=12)

    assert pick.owner_id == user.id
    assert pick.player_id == target.id

    ledger_entries = (
        db_session.query(models.EconomicLedger)
        .filter(
            models.EconomicLedger.league_id == league.id,
            models.EconomicLedger.currency_type == "FAAB",
            models.EconomicLedger.transaction_type == "WAIVER_CLAIM_BID",
            models.EconomicLedger.reference_id == str(pick.id),
        )
        .all()
    )
    assert len(ledger_entries) == 1
    assert ledger_entries[0].amount == 12
    assert ledger_entries[0].from_owner_id == user.id
    assert ledger_entries[0].to_owner_id is None


def test_process_claim_rejects_when_ledger_balance_insufficient(db_session):
    league = make_league(db_session)
    user = make_user(db_session, league, "waiver-owner-2")
    target = make_player(db_session, "Target2")

    db_session.add(
        models.EconomicLedger(
            league_id=league.id,
            season_year=2026,
            currency_type="FAAB",
            amount=5,
            from_owner_id=None,
            to_owner_id=user.id,
            transaction_type="SEASON_ALLOCATION",
            reference_type="LEAGUE_SETTINGS",
            reference_id=f"{league.id}:2026",
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        process_claim(db_session, user=user, player_id=target.id, bid=10)

    assert exc.value.status_code == 400
    assert "Insufficient FAAB balance" in exc.value.detail


def test_process_claim_rejects_after_commissioner_waiver_deadline(db_session):
    league = make_league(db_session)
    user = make_user(db_session, league, "waiver-owner-deadline")
    target = make_player(db_session, "Deadline Target")

    db_session.add(
        models.LeagueSettings(
            league_id=league.id,
            waiver_deadline="2000-01-01T00:00:00Z",
            roster_size=14,
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        process_claim(db_session, user=user, player_id=target.id, bid=0)

    assert exc.value.status_code == 400
    assert "Waiver claims are closed by commissioner rule" in str(exc.value.detail)


def test_process_claim_rejects_suppressed_position(db_session):
    league = make_league(db_session)
    user = make_user(db_session, league, "waiver-owner-suppressed")
    target = models.Player(name="Suppressed Kicker", position="K", nfl_team="ABC")
    db_session.add(target)
    db_session.add(
        models.LeagueSettings(
            league_id=league.id,
            starting_slots={
                "QB": 1,
                "RB": 2,
                "WR": 2,
                "TE": 1,
                "K": 0,
                "DEF": 1,
                "FLEX": 1,
                "MAX_QB": 1,
                "MAX_RB": 3,
                "MAX_WR": 3,
                "MAX_TE": 2,
                "MAX_K": 0,
                "MAX_DEF": 1,
                "MAX_FLEX": 1,
            },
        )
    )
    db_session.commit()
    db_session.refresh(target)

    with pytest.raises(HTTPException) as exc:
        process_claim(db_session, user=user, player_id=target.id, bid=0)

    assert exc.value.status_code == 400
    assert "disabled for this league" in exc.value.detail


def test_player_pools_respect_league_scoped_position_suppression(db_session):
    league = make_league(db_session)
    user = make_user(db_session, league, "waiver-owner-pools")
    db_session.add(
        models.LeagueSettings(
            league_id=league.id,
            starting_slots={
                "QB": 1,
                "RB": 2,
                "WR": 2,
                "TE": 1,
                "K": 0,
                "DEF": 1,
                "FLEX": 1,
                "MAX_QB": 1,
                "MAX_RB": 3,
                "MAX_WR": 3,
                "MAX_TE": 2,
                "MAX_K": 0,
                "MAX_DEF": 1,
                "MAX_FLEX": 1,
            },
        )
    )
    kicker = models.Player(name="Suppressed Pool Kicker", position="K", nfl_team="ABC")
    runner = models.Player(name="Eligible Pool Runner", position="RB", nfl_team="ABC")
    db_session.add_all([kicker, runner])
    db_session.commit()

    free_agents = get_league_free_agents(db_session, league.id)
    free_agent_positions = {player.position for player in free_agents}
    assert "K" not in free_agent_positions
    assert "RB" in free_agent_positions

    search_results = search_all_players(db_session, "Pool", "ALL", league.id)
    search_positions = {player.position for player in search_results}
    assert "K" not in search_positions
    assert "RB" in search_positions
