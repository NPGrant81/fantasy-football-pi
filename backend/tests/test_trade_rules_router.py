import sys
from pathlib import Path
import secrets

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.league import get_trade_rules, update_trade_rules, TradeRulesSchema


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
    league = models.League(name=f"L-{secrets.token_hex(4)}")
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def make_member(db, league, username=None):
    username = username or secrets.token_hex(4)
    user = models.User(
        username=username,
        hashed_password="pw",
        league_id=league.id,
        team_name=f"Team-{username}",
        is_commissioner=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_commissioner(db, league, username=None):
    username = username or secrets.token_hex(4)
    user = models.User(
        username=username,
        hashed_password="pw",
        league_id=league.id,
        team_name=f"Team-{username}",
        is_commissioner=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- GET tests ---

def test_trade_rules_get_member_success(db_session):
    """League member can GET trade rules; defaults returned when no settings row exists."""
    league = make_league(db_session)
    member = make_member(db_session, league)

    result = get_trade_rules(league_id=league.id, current_user=member, db=db_session)

    assert isinstance(result, TradeRulesSchema)
    assert result.trade_deadline is None
    assert result.allow_playoff_trades is True


def test_trade_rules_get_non_member_forbidden(db_session):
    """User from a different league gets 403 on GET."""
    league_a = make_league(db_session)
    league_b = make_league(db_session)
    outsider = make_member(db_session, league_b)

    with pytest.raises(HTTPException) as exc_info:
        get_trade_rules(league_id=league_a.id, current_user=outsider, db=db_session)

    assert exc_info.value.status_code == 403


def test_trade_rules_get_returns_persisted_values(db_session):
    """GET reflects values previously stored in LeagueSettings."""
    league = make_league(db_session)
    member = make_member(db_session, league)
    settings = models.LeagueSettings(
        league_id=league.id,
        trade_deadline="2026-04-01T18:00:00Z",
        allow_playoff_trades=False,
        trade_veto_enabled=True,
        trade_veto_threshold=3,
    )
    db_session.add(settings)
    db_session.commit()

    result = get_trade_rules(league_id=league.id, current_user=member, db=db_session)

    assert result.trade_deadline == "2026-04-01T18:00:00Z"
    assert result.allow_playoff_trades is False
    assert result.trade_veto_enabled is True
    assert result.trade_veto_threshold == 3


# --- PUT tests ---

def test_trade_rules_put_commissioner_success(db_session):
    """Commissioner can PUT trade rules and values round-trip via GET."""
    league = make_league(db_session)
    commissioner = make_commissioner(db_session, league)

    payload = TradeRulesSchema(
        trade_deadline="2026-05-01T12:00:00Z",
        allow_playoff_trades=False,
        require_commissioner_approval=False,
        trade_veto_enabled=True,
        trade_veto_threshold=2,
        trade_review_period_hours=48,
        trade_max_players_per_side=5,
        trade_league_vote_enabled=False,
        trade_league_vote_threshold=None,
    )

    result = update_trade_rules(
        league_id=league.id, payload=payload, current_user=commissioner, db=db_session
    )

    assert result.trade_deadline == "2026-05-01T12:00:00Z"
    assert result.allow_playoff_trades is False
    assert result.trade_veto_enabled is True
    assert result.trade_veto_threshold == 2
    assert result.trade_review_period_hours == 48
    assert result.trade_max_players_per_side == 5

    # Verify GET returns the same data
    fetched = get_trade_rules(league_id=league.id, current_user=commissioner, db=db_session)
    assert fetched.trade_deadline == "2026-05-01T12:00:00Z"
    assert fetched.trade_veto_threshold == 2


def test_trade_rules_put_non_commissioner_forbidden(db_session):
    """Non-commissioner member gets 403 on PUT."""
    league = make_league(db_session)
    member = make_member(db_session, league)

    payload = TradeRulesSchema()
    with pytest.raises(HTTPException) as exc_info:
        update_trade_rules(
            league_id=league.id, payload=payload, current_user=member, db=db_session
        )

    assert exc_info.value.status_code == 403


def test_trade_rules_put_commissioner_wrong_league_forbidden(db_session):
    """Commissioner from a different league gets 403 on PUT."""
    league_a = make_league(db_session)
    league_b = make_league(db_session)
    commissioner_b = make_commissioner(db_session, league_b)

    payload = TradeRulesSchema()
    with pytest.raises(HTTPException) as exc_info:
        update_trade_rules(
            league_id=league_a.id, payload=payload, current_user=commissioner_b, db=db_session
        )

    assert exc_info.value.status_code == 403


def test_trade_rules_put_invalid_deadline_returns_400(db_session):
    """PUT with a non-timezone-aware trade_deadline returns 400."""
    league = make_league(db_session)
    commissioner = make_commissioner(db_session, league)

    for bad_deadline in ("2026-04-01", "Wed 11PM", "April 1st 2026"):
        payload = TradeRulesSchema(trade_deadline=bad_deadline)
        with pytest.raises(HTTPException) as exc_info:
            update_trade_rules(
                league_id=league.id, payload=payload, current_user=commissioner, db=db_session
            )
        assert exc_info.value.status_code == 400


def test_trade_rules_put_valid_deadline_formats_accepted(db_session):
    """PUT accepts valid timezone-aware ISO-8601 deadline formats."""
    league = make_league(db_session)
    commissioner = make_commissioner(db_session, league)

    for valid_deadline in ("2026-04-01T18:00:00Z", "2026-04-01T18:00:00+00:00"):
        payload = TradeRulesSchema(trade_deadline=valid_deadline)
        result = update_trade_rules(
            league_id=league.id, payload=payload, current_user=commissioner, db=db_session
        )
        assert result.trade_deadline == valid_deadline


def test_trade_rules_put_null_deadline_accepted(db_session):
    """PUT with null/empty trade_deadline clears the deadline."""
    league = make_league(db_session)
    commissioner = make_commissioner(db_session, league)
    # Set a deadline first
    db_session.add(models.LeagueSettings(league_id=league.id, trade_deadline="2026-04-01T18:00:00Z"))
    db_session.commit()

    payload = TradeRulesSchema(trade_deadline=None)
    result = update_trade_rules(
        league_id=league.id, payload=payload, current_user=commissioner, db=db_session
    )
    assert result.trade_deadline is None


def test_trade_rules_put_veto_threshold_required_when_veto_enabled(db_session):
    """PUT with veto enabled but no threshold returns 400."""
    league = make_league(db_session)
    commissioner = make_commissioner(db_session, league)

    payload = TradeRulesSchema(trade_veto_enabled=True, trade_veto_threshold=None)
    with pytest.raises(HTTPException) as exc_info:
        update_trade_rules(
            league_id=league.id, payload=payload, current_user=commissioner, db=db_session
        )
    assert exc_info.value.status_code == 400


def test_trade_rules_put_vote_threshold_bounds_enforced(db_session):
    """League vote threshold must be 1–100 when league vote is enabled."""
    league = make_league(db_session)
    commissioner = make_commissioner(db_session, league)

    for bad_threshold in (0, 101, -5):
        payload = TradeRulesSchema(
            trade_league_vote_enabled=True, trade_league_vote_threshold=bad_threshold
        )
        with pytest.raises(HTTPException) as exc_info:
            update_trade_rules(
                league_id=league.id, payload=payload, current_user=commissioner, db=db_session
            )
        assert exc_info.value.status_code == 400
