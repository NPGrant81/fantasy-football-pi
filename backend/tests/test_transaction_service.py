import sys
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.services.transaction_service import (
    log_transaction,
    get_owner_at_time,
    get_acquisition_method,
)


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


def make_league(db, name="L"):
    league = models.League(name=name)
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def make_player(db, name="P"):
    p = models.Player(name=name, position="RB", nfl_team="ABC")
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


def test_owner_at_time_and_acquisition(db_session):
    league = make_league(db_session)
    player = make_player(db_session)
    u1 = make_user(db_session, league, "u1")
    u2 = make_user(db_session, league, "u2")

    # draft: u1 gets player at t0 (we'll manually set the timestamp afterwards)
    t0 = datetime.utcnow() - timedelta(days=10)
    tx1 = log_transaction(
        db_session,
        league.id,
        player.id,
        old_owner_id=None,
        new_owner_id=u1.id,
        transaction_type="draft",
        notes="initial draft",
    )
    # backdate the draft record so our time queries make sense
    db_session.execute(
        models.TransactionHistory.__table__.update()
        .where(models.TransactionHistory.id == tx1.id)
        .values(timestamp=t0)
    )
    db_session.commit()

    # trade: player moves to u2 at t1
    t1 = datetime.utcnow() - timedelta(days=5)
    tx2 = log_transaction(
        db_session,
        league.id,
        player.id,
        old_owner_id=u1.id,
        new_owner_id=u2.id,
        transaction_type="trade",
        notes="package deal",
    )
    # manually adjust timestamp for testing convenience
    db_session.execute(
        models.TransactionHistory.__table__.update()
        .where(models.TransactionHistory.id == tx2.id)
        .values(timestamp=t1)
    )
    db_session.commit()

    # verify owner at various times
    assert get_owner_at_time(db_session, player.id, t0 + timedelta(hours=1)) == u1.id
    assert get_owner_at_time(db_session, player.id, datetime.utcnow()) == u2.id

    # acquisition methods
    assert get_acquisition_method(db_session, player.id, u1.id) == "DRAFT"
    assert get_acquisition_method(db_session, player.id, u2.id) == "TRADE"


def test_no_history_returns_none(db_session):
    assert get_owner_at_time(db_session, 999, datetime.utcnow()) is None
    assert get_acquisition_method(db_session, 999, 1) is None
