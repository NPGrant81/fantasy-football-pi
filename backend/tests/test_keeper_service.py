import sys
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.services.keeper_service import compute_keeper_flags
from backend.services.transaction_service import log_transaction


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


def make_player(db):
    p = models.Player(name="P", position="RB", nfl_team="ABC")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def make_user(db, league, username="u"):
    u = models.User(username=username, hashed_password="pw", league_id=league.id)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def make_rules(db, league, **kwargs):
    r = models.KeeperRules(league_id=league.id, **kwargs)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_flags_for_waiver_and_trade_and_drop(db_session):
    league = make_league(db_session)
    player = make_player(db_session)
    u1 = make_user(db_session, league, "u1")
    u2 = make_user(db_session, league, "u2")

    # create rules with all policies enabled and a trade_deadline in the past
    deadline = datetime.utcnow() - timedelta(days=1)
    rules = make_rules(db_session, league, waiver_policy=True, trade_deadline=deadline, drafted_only=True)

    # log initial draft to u1
    log_transaction(db_session, league.id, player.id, None, u1.id, "draft")
    # simulate drop and waiver pick-up
    log_transaction(db_session, league.id, player.id, u1.id, None, "drop")
    log_transaction(db_session, league.id, player.id, None, u1.id, "waiver_add")
    # now trade to u2 after the deadline
    log_transaction(db_session, league.id, player.id, u1.id, u2.id, "trade")

    # compute flags for both owners
    flags_u1 = compute_keeper_flags(db_session, league.id, player.id, u1.id, rules)
    flags_u2 = compute_keeper_flags(db_session, league.id, player.id, u2.id, rules)

    # u1 should be flagged for waiver and drop
    assert flags_u1["flag_waiver"] is True
    assert flags_u1["flag_drop"] is True
    # trade flag only applies if owner_at_deadline != owner_id (u2 was not owner at deadline)
    assert flags_u1["flag_trade"] is True

    # u2 should be flagged for trade (was not owner at deadline) but not waiver/drop
    assert flags_u2["flag_waiver"] is False
    assert flags_u2["flag_drop"] is False
    assert flags_u2["flag_trade"] is True
