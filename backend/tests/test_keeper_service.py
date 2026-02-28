import sys
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.services.keeper_service import (
    compute_keeper_flags,
    get_effective_budget,
    project_budget,
    lock_keepers_for_league,
    compute_surplus_recommendations,
    veto_keepers,
    reset_keepers,
    send_window_open_notifications,
    send_deadline_reminder,
    send_veto_alert,
)
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


def test_budget_and_lock_logic(db_session):
    league = make_league(db_session)
    player = make_player(db_session)
    owner = make_user(db_session, league, "owner")
    # set starting budget on user
    owner.future_draft_budget = 200
    db_session.commit()

    # create a pending keeper
    k = models.Keeper(
        league_id=league.id,
        owner_id=owner.id,
        player_id=player.id,
        season=2026,
        keep_cost=20,
        status="pending",
    )
    db_session.add(k)
    db_session.commit()

    # projected budget should subtract pending
    assert project_budget(db_session, owner.id) == 180
    # effective (locked) budget still 200
    assert get_effective_budget(db_session, owner.id) == 200

    # lock keepers for league and observe budget deduction
    count = lock_keepers_for_league(db_session, league.id, 2026)
    assert count == 1
    # owner's budget updated
    owner_ref = db_session.query(models.User).get(owner.id)
    assert owner_ref.future_draft_budget == 180
    # keeper status changed and locked_at populated
    updated = db_session.query(models.Keeper).get(k.id)
    assert updated.status == "locked"
    assert updated.locked_at is not None


def test_recommendations_and_years(db_session, monkeypatch):
    league = make_league(db_session)
    owner = make_user(db_session, league, "o")
    # create keeper entries with different costs
    p1 = make_player(db_session)
    p2 = make_player(db_session)
    # two keepers already kept once
    k1 = models.Keeper(league_id=league.id, owner_id=owner.id, player_id=p1.id, season=2026, keep_cost=10, years_kept_count=1)
    k2 = models.Keeper(league_id=league.id, owner_id=owner.id, player_id=p2.id, season=2026, keep_cost=5, years_kept_count=2)
    db_session.add_all([k1, k2])
    db_session.commit()
    # make rules with max_keepers 1 and max_years 2
    make_rules(db_session, league, max_keepers=1, max_years_per_player=2)

    # patch projection_service to return fixed values
    from backend.services import projection_service
    monkeypatch.setattr(projection_service, "get_projected_auction_value", lambda db, pid, s: 50 if pid == p1.id else 100)

    recs = compute_surplus_recommendations(db_session, owner.id, 2026)
    # only one recommendation because limit=1 and p2 has higher surplus but has already 2 years (equal to max_years)
    assert len(recs) == 1
    assert recs[0]["player_id"] == p1.id
    assert recs[0]["recommended"] is True


def test_veto_and_reset(db_session):
    league = make_league(db_session)
    owner = make_user(db_session, league, "owner2")
    player = make_player(db_session)
    k = models.Keeper(league_id=league.id, owner_id=owner.id, player_id=player.id, season=2026, keep_cost=10, status="locked")
    db_session.add(k)
    db_session.commit()
    # veto should unlock
    n = veto_keepers(db_session, owner.id, league.id, 2026)
    assert n == 1
    refreshed = db_session.query(models.Keeper).get(k.id)
    assert refreshed.status == "pending"
    assert refreshed.locked_at is None

    # reset removes all keepers
    reset_count = reset_keepers(db_session, league.id, 2026)
    assert reset_count == 1
    assert db_session.query(models.Keeper).filter(models.Keeper.league_id == league.id).count() == 0


def test_notification_helpers(db_session, monkeypatch):
    league = make_league(db_session)
    # create two users
    u1 = make_user(db_session, league, "u1")
    u2 = make_user(db_session, league, "u2")
    calls = []
    monkeypatch.setattr(
        'backend.services.notifications.NotifyService.send_transactional_email',
        lambda user_id, template_id, context: calls.append((user_id, template_id, context))
    )
    # window open
    send_window_open_notifications(db_session, league.id)
    assert len(calls) == 2
    assert calls[0][1] == 'keeper_window_open'
    calls.clear()
    # deadline reminder
    send_deadline_reminder(db_session, league.id)
    assert len(calls) == 2
    assert calls[0][1] == 'keeper_deadline_reminder'
    calls.clear()
    # veto alert
    send_veto_alert(db_session, u1.id, league.id)
    assert len(calls) == 1
    assert calls[0][1] == 'keeper_veto_alert'
