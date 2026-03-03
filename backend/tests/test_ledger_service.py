import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.services.ledger_service import owner_balance, record_ledger_entry


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
    l = models.League(name="L-LEDGER")
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def make_user(db, league, username="u"):
    u = models.User(username=username, hashed_password="pw", league_id=league.id)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_owner_balance_derived_from_ledger_sum(db_session):
    league = make_league(db_session)
    owner1 = make_user(db_session, league, "owner-ledger-1")
    owner2 = make_user(db_session, league, "owner-ledger-2")

    # opening allocation +200 to owner1 for 2026
    record_ledger_entry(
        db_session,
        league_id=league.id,
        season_year=2026,
        currency_type="DRAFT_DOLLARS",
        amount=200,
        from_owner_id=None,
        to_owner_id=owner1.id,
        transaction_type="SEASON_ALLOCATION",
        reference_type="LEAGUE_SETTINGS",
        reference_id=f"{league.id}:2026",
    )

    # owner1 sends 25 to owner2
    record_ledger_entry(
        db_session,
        league_id=league.id,
        season_year=2026,
        currency_type="DRAFT_DOLLARS",
        amount=25,
        from_owner_id=owner1.id,
        to_owner_id=owner2.id,
        transaction_type="TRADE_DOLLARS",
        reference_type="TRADE_PROPOSAL",
        reference_id="123",
    )

    db_session.commit()

    assert owner_balance(
        db_session,
        league_id=league.id,
        owner_id=owner1.id,
        currency_type="DRAFT_DOLLARS",
        season_year=2026,
    ) == 175

    assert owner_balance(
        db_session,
        league_id=league.id,
        owner_id=owner2.id,
        currency_type="DRAFT_DOLLARS",
        season_year=2026,
    ) == 25


def test_ledger_is_append_only(db_session):
    league = make_league(db_session)
    owner = make_user(db_session, league, "owner-ledger-append")

    entry = record_ledger_entry(
        db_session,
        league_id=league.id,
        season_year=2026,
        currency_type="FAAB",
        amount=100,
        from_owner_id=None,
        to_owner_id=owner.id,
        transaction_type="SEASON_ALLOCATION",
        reference_type="LEAGUE_SETTINGS",
        reference_id=f"{league.id}:2026:faab",
    )
    db_session.commit()

    # update should be blocked
    entry.notes = "attempt to mutate"
    with pytest.raises(ValueError):
        db_session.commit()
    db_session.rollback()

    # delete should also be blocked
    db_session.delete(entry)
    with pytest.raises(ValueError):
        db_session.commit()
    db_session.rollback()
