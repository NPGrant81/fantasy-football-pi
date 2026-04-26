"""Unit tests for trade audit history (#354).

Covers trade_event_service.record_trade_event:
- Event persisted with correct fields (type, actor, comment)
- comment is None when blank/whitespace
- event_type is uppercased and stripped
- actor_user_id can be None (system events)
- metadata_json stored and retrieved correctly

Covers history endpoint ordering and completeness:
- Events returned in chronological insertion order
- SUBMITTED + APPROVED timeline present after approval
- SUBMITTED + REJECTED timeline present after rejection
- History returns empty list for trade with no events
- History is scoped to trade (other trade events not leaked)
- History endpoint returns 404 for unknown trade
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.core.security import get_current_user
from backend.database import get_db
from backend.main import app
from backend.services.trade_event_service import record_trade_event


# ─── Direct service tests ──────────────────────────────────────────────────────

def setup_db():
    engine = create_engine("sqlite:///:memory:")
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return session()


def make_trade(db, league_name="AuditLeague"):
    league = models.League(name=league_name, current_season=2026)
    db.add(league)
    db.flush()
    u1 = models.User(username="u1", hashed_password="pw", league_id=league.id)
    u2 = models.User(username="u2", hashed_password="pw", league_id=league.id)
    db.add_all([u1, u2])
    db.flush()
    trade = models.Trade(league_id=league.id, team_a_id=u1.id, team_b_id=u2.id, status="PENDING")
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade, u1


def test_record_trade_event_persists_correct_fields():
    """Event rows are written with type, actor_user_id, and comment."""
    db = setup_db()
    trade, actor = make_trade(db)

    record_trade_event(db, trade_id=trade.id, event_type="submitted", actor_user_id=actor.id, comment="first submission")
    db.commit()

    events = db.query(models.TradeEvent).filter_by(trade_id=trade.id).all()
    assert len(events) == 1
    e = events[0]
    assert e.event_type == "SUBMITTED"   # uppercased
    assert e.actor_user_id == actor.id
    assert e.comment == "first submission"


def test_record_trade_event_strips_whitespace_from_type():
    """event_type is stripped and uppercased regardless of input casing."""
    db = setup_db()
    trade, actor = make_trade(db, league_name="League2")

    record_trade_event(db, trade_id=trade.id, event_type="  Approved  ", actor_user_id=actor.id)
    db.commit()

    event = db.query(models.TradeEvent).filter_by(trade_id=trade.id).first()
    assert event.event_type == "APPROVED"


def test_record_trade_event_blank_comment_stored_as_none():
    """Blank/whitespace-only comment is stored as None."""
    db = setup_db()
    trade, actor = make_trade(db, league_name="League3")

    record_trade_event(db, trade_id=trade.id, event_type="REJECTED", actor_user_id=actor.id, comment="   ")
    db.commit()

    event = db.query(models.TradeEvent).filter_by(trade_id=trade.id).first()
    assert event.comment is None


def test_record_trade_event_no_comment():
    """comment defaults to None when omitted."""
    db = setup_db()
    trade, actor = make_trade(db, league_name="League4")

    record_trade_event(db, trade_id=trade.id, event_type="SUBMITTED", actor_user_id=actor.id)
    db.commit()

    event = db.query(models.TradeEvent).filter_by(trade_id=trade.id).first()
    assert event.comment is None


def test_record_trade_event_system_event_no_actor():
    """actor_user_id can be None for system-generated events."""
    db = setup_db()
    trade, _ = make_trade(db, league_name="League5")

    record_trade_event(db, trade_id=trade.id, event_type="SYSTEM_NOTE", actor_user_id=None)
    db.commit()

    event = db.query(models.TradeEvent).filter_by(trade_id=trade.id).first()
    assert event.actor_user_id is None
    assert event.event_type == "SYSTEM_NOTE"


def test_record_trade_event_metadata_json_stored():
    """metadata_json dict is persisted and retrievable."""
    db = setup_db()
    trade, actor = make_trade(db, league_name="League6")
    payload = {"player_moved": 42, "from_team": 1}

    record_trade_event(db, trade_id=trade.id, event_type="APPROVED", actor_user_id=actor.id, metadata_json=payload)
    db.commit()

    event = db.query(models.TradeEvent).filter_by(trade_id=trade.id).first()
    assert event.metadata_json == payload


def test_record_multiple_events_all_persisted():
    """Multiple events on the same trade all persist independently."""
    db = setup_db()
    trade, actor = make_trade(db, league_name="League7")

    record_trade_event(db, trade_id=trade.id, event_type="SUBMITTED", actor_user_id=actor.id)
    record_trade_event(db, trade_id=trade.id, event_type="APPROVED", actor_user_id=actor.id, comment="OK")
    db.commit()

    events = db.query(models.TradeEvent).filter_by(trade_id=trade.id).all()
    types = {e.event_type for e in events}
    assert types == {"SUBMITTED", "APPROVED"}


# ─── History endpoint tests (via TestClient) ──────────────────────────────────

@pytest.fixture
def api_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_db(api_db):
    def _override():
        try:
            yield api_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()


def _seed_league_for_history(api_db, league_name="HistoryLeague"):
    league = models.League(name=league_name, current_season=2026)
    api_db.add(league)
    api_db.commit()
    api_db.refresh(league)

    api_db.add(models.LeagueSettings(league_id=league.id, roster_size=15))

    team_a = models.User(username=f"ha-{league.id}", hashed_password="pw", league_id=league.id, future_draft_budget=30)
    team_b = models.User(username=f"hb-{league.id}", hashed_password="pw", league_id=league.id, future_draft_budget=20)
    commissioner = models.User(
        username=f"hc-{league.id}", hashed_password="pw", league_id=league.id,
        is_commissioner=True, future_draft_budget=0
    )
    api_db.add_all([team_a, team_b, commissioner])
    api_db.commit()
    for obj in (team_a, team_b, commissioner):
        api_db.refresh(obj)

    p_a = models.Player(name=f"HP_A_{league.id}", position="RB", nfl_team="X")
    p_b = models.Player(name=f"HP_B_{league.id}", position="WR", nfl_team="Y")
    api_db.add_all([p_a, p_b])
    api_db.commit()
    api_db.refresh(p_a)
    api_db.refresh(p_b)

    api_db.add(models.DraftPick(league_id=league.id, owner_id=team_a.id, player_id=p_a.id, year=2027))
    api_db.add(models.DraftPick(league_id=league.id, owner_id=team_b.id, player_id=p_b.id, year=2027))
    api_db.commit()

    return {"league": league, "team_a": team_a, "team_b": team_b, "commissioner": commissioner,
            "player_a": p_a, "player_b": p_b}


def test_history_endpoint_returns_submitted_event(client, api_db):
    """After submitting a trade, history contains exactly one SUBMITTED event."""
    seeded = _seed_league_for_history(api_db, "HistLeagueA")
    app.dependency_overrides[get_current_user] = lambda: seeded["team_a"]

    resp = client.post(
        f"/trades/leagues/{seeded['league'].id}/submit-v2",
        json={
            "team_a_id": seeded["team_a"].id,
            "team_b_id": seeded["team_b"].id,
            "assets_from_a": [{"asset_type": "PLAYER", "player_id": seeded["player_a"].id}],
            "assets_from_b": [{"asset_type": "PLAYER", "player_id": seeded["player_b"].id}],
        },
    )
    assert resp.status_code == 200
    trade_id = resp.json()["trade_id"]

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    history_resp = client.get(f"/trades/leagues/{seeded['league'].id}/{trade_id}/history-v2")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == 1
    assert history[0]["event_type"] == "SUBMITTED"


def test_history_endpoint_approve_shows_submitted_then_approved(client, api_db):
    """Approved trade history shows SUBMITTED then APPROVED in order."""
    seeded = _seed_league_for_history(api_db, "HistLeagueB")

    app.dependency_overrides[get_current_user] = lambda: seeded["team_a"]
    submit = client.post(
        f"/trades/leagues/{seeded['league'].id}/submit-v2",
        json={
            "team_a_id": seeded["team_a"].id,
            "team_b_id": seeded["team_b"].id,
            "assets_from_a": [{"asset_type": "PLAYER", "player_id": seeded["player_a"].id}],
            "assets_from_b": [{"asset_type": "PLAYER", "player_id": seeded["player_b"].id}],
        },
    )
    assert submit.status_code == 200
    trade_id = submit.json()["trade_id"]

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    approve = client.post(
        f"/trades/leagues/{seeded['league'].id}/{trade_id}/approve-v2",
        json={"commissioner_comments": "Looks good"},
    )
    assert approve.status_code == 200

    history_resp = client.get(f"/trades/leagues/{seeded['league'].id}/{trade_id}/history-v2")
    assert history_resp.status_code == 200
    history = history_resp.json()
    event_types = [e["event_type"] for e in history]
    assert event_types == ["SUBMITTED", "APPROVED"]


def test_history_endpoint_reject_shows_submitted_then_rejected(client, api_db):
    """Rejected trade history shows SUBMITTED then REJECTED with comment."""
    seeded = _seed_league_for_history(api_db, "HistLeagueC")

    app.dependency_overrides[get_current_user] = lambda: seeded["team_a"]
    submit = client.post(
        f"/trades/leagues/{seeded['league'].id}/submit-v2",
        json={
            "team_a_id": seeded["team_a"].id,
            "team_b_id": seeded["team_b"].id,
            "assets_from_a": [{"asset_type": "PLAYER", "player_id": seeded["player_a"].id}],
            "assets_from_b": [{"asset_type": "PLAYER", "player_id": seeded["player_b"].id}],
        },
    )
    assert submit.status_code == 200
    trade_id = submit.json()["trade_id"]

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    reject = client.post(
        f"/trades/leagues/{seeded['league'].id}/{trade_id}/reject-v2",
        json={"commissioner_comments": "Too one-sided"},
    )
    assert reject.status_code == 200

    history_resp = client.get(f"/trades/leagues/{seeded['league'].id}/{trade_id}/history-v2")
    history = history_resp.json()
    event_types = [e["event_type"] for e in history]
    assert event_types == ["SUBMITTED", "REJECTED"]
    assert history[-1]["comment"] == "Too one-sided"


def test_history_endpoint_scoped_to_trade(client, api_db):
    """Events from a different trade do not appear in this trade's history."""
    seeded = _seed_league_for_history(api_db, "HistLeagueD")
    app.dependency_overrides[get_current_user] = lambda: seeded["team_a"]

    # Submit one trade and capture its ID
    s1 = client.post(
        f"/trades/leagues/{seeded['league'].id}/submit-v2",
        json={
            "team_a_id": seeded["team_a"].id,
            "team_b_id": seeded["team_b"].id,
            "assets_from_a": [{"asset_type": "DRAFT_DOLLARS", "amount": 5}],
            "assets_from_b": [{"asset_type": "DRAFT_DOLLARS", "amount": 3}],
        },
    )
    assert s1.status_code == 200
    trade1_id = s1.json()["trade_id"]

    # Submit a second real trade so scoping excludes events from another valid trade.
    s2 = client.post(
        f"/trades/leagues/{seeded['league'].id}/submit-v2",
        json={
            "team_a_id": seeded["team_a"].id,
            "team_b_id": seeded["team_b"].id,
            "assets_from_a": [{"asset_type": "PLAYER", "player_id": seeded["player_a"].id}],
            "assets_from_b": [{"asset_type": "PLAYER", "player_id": seeded["player_b"].id}],
        },
    )
    assert s2.status_code == 200
    trade2_id = s2.json()["trade_id"]

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    approve_second = client.post(
        f"/trades/leagues/{seeded['league'].id}/{trade2_id}/approve-v2",
        json={"commissioner_comments": "approve second trade"},
    )
    assert approve_second.status_code == 200

    history_resp = client.get(f"/trades/leagues/{seeded['league'].id}/{trade1_id}/history-v2")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == 1
    assert history[0]["event_type"] == "SUBMITTED"
    assert all(e["trade_id"] == trade1_id for e in history)


def test_history_endpoint_returns_empty_list_for_trade_with_no_events(client, api_db):
    """Trade with no TradeEvent rows returns an empty history list."""
    seeded = _seed_league_for_history(api_db, "HistLeagueNoEvents")

    no_event_trade = models.Trade(
        league_id=seeded["league"].id,
        team_a_id=seeded["team_a"].id,
        team_b_id=seeded["team_b"].id,
        status="PENDING",
    )
    api_db.add(no_event_trade)
    api_db.commit()
    api_db.refresh(no_event_trade)

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    history_resp = client.get(
        f"/trades/leagues/{seeded['league'].id}/{no_event_trade.id}/history-v2"
    )
    assert history_resp.status_code == 200
    assert history_resp.json() == []


def test_history_endpoint_returns_404_for_unknown_trade(client, api_db):
    """GET history for a non-existent trade returns 404."""
    seeded = _seed_league_for_history(api_db, "HistLeagueE")
    app.dependency_overrides[get_current_user] = lambda: seeded["team_a"]

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    resp = client.get(f"/trades/leagues/{seeded['league'].id}/9999999/history-v2")
    assert resp.status_code == 404


def test_history_response_includes_actor_and_trade_id(client, api_db):
    """Each history row contains trade_id, event_type, and actor_user_id."""
    seeded = _seed_league_for_history(api_db, "HistLeagueF")
    app.dependency_overrides[get_current_user] = lambda: seeded["team_a"]

    resp = client.post(
        f"/trades/leagues/{seeded['league'].id}/submit-v2",
        json={
            "team_a_id": seeded["team_a"].id,
            "team_b_id": seeded["team_b"].id,
            "assets_from_a": [{"asset_type": "DRAFT_DOLLARS", "amount": 2}],
            "assets_from_b": [{"asset_type": "DRAFT_DOLLARS", "amount": 1}],
        },
    )
    trade_id = resp.json()["trade_id"]

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    history_resp = client.get(f"/trades/leagues/{seeded['league'].id}/{trade_id}/history-v2")
    row = history_resp.json()[0]
    assert row["trade_id"] == trade_id
    assert "event_type" in row
    assert "actor_user_id" in row
