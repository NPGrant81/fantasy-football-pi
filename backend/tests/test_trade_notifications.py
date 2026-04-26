"""Tests for trade notification service (#355 + #356).

Covers notify_trade_approved (Phase 6 completion email):
- Correct template_id used
- Both team_a and team_b receive the notification
- Commissioner comments included in context
- Context contains league_id, trade_id, status
- Returns count of emails sent (2)
- Works when commissioner_comments is None

Covers notify_trade_rejected (Phase 6 rejection email):
- Correct template_id used
- Both team_a and team_b receive the notification
- rejection_reason matches commissioner_comments when present
- has_rejection_reason is True when reason present, False otherwise
- Context contains league_id, trade_id, status
- Returns count of emails sent (2)
- Works when commissioner_comments is None (reason → None, has_rejection_reason → False)

Covers notify_trade_submitted:
- Correct template_id used
- Commissioner(s) notified
- Both teams notified (except submitter)
- Submitting user excluded from recipients
- Returns count of notifications sent

Covers router integration (notify called after approve/reject):
- notify_trade_approved called after successful approve-v2
- notify_trade_rejected called after reject-v2
- Notification failure does not roll back trade status
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.core.security import get_current_user
from backend.database import get_db
from backend.main import app
from backend.services import trade_notification_service
from backend.services.trade_notification_service import (
    notify_trade_approved,
    notify_trade_rejected,
    notify_trade_submitted,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_trade(
    trade_id=1,
    league_id=10,
    team_a_id=101,
    team_b_id=102,
    status="APPROVED",
    commissioner_comments=None,
):
    trade = MagicMock(spec=models.Trade)
    trade.id = trade_id
    trade.league_id = league_id
    trade.team_a_id = team_a_id
    trade.team_b_id = team_b_id
    trade.status = status
    trade.commissioner_comments = commissioner_comments
    return trade


# ─── notify_trade_approved tests (#355) ───────────────────────────────────────

def test_notify_trade_approved_uses_correct_template():
    trade = _make_trade(status="APPROVED")
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_approved(trade)
    for c in mock_send.call_args_list:
        assert c.kwargs["template_id"] == "trade_approved"


def test_notify_trade_approved_notifies_both_teams():
    trade = _make_trade(team_a_id=101, team_b_id=102)
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_approved(trade)
    notified_users = {c.kwargs["user_id"] for c in mock_send.call_args_list}
    assert notified_users == {101, 102}


def test_notify_trade_approved_returns_sent_count():
    trade = _make_trade(team_a_id=1, team_b_id=2)
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email"):
        count = notify_trade_approved(trade)
    assert count == 2


def test_notify_trade_approved_context_includes_comments():
    trade = _make_trade(commissioner_comments="All good", status="APPROVED")
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_approved(trade)
    contexts = [c.kwargs["context"] for c in mock_send.call_args_list]
    for ctx in contexts:
        assert ctx["commissioner_comments"] == "All good"
        assert ctx["status"] == "APPROVED"
        assert ctx["trade_id"] == trade.id
        assert ctx["league_id"] == trade.league_id


def test_notify_trade_approved_none_comments_included():
    """When commissioner leaves no comment, context still passes None gracefully."""
    trade = _make_trade(commissioner_comments=None)
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_approved(trade)
    for c in mock_send.call_args_list:
        assert c.kwargs["context"]["commissioner_comments"] is None


# ─── notify_trade_rejected tests (#356) ───────────────────────────────────────

def test_notify_trade_rejected_uses_correct_template():
    trade = _make_trade(status="REJECTED", commissioner_comments="Imbalanced")
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_rejected(trade)
    for c in mock_send.call_args_list:
        assert c.kwargs["template_id"] == "trade_rejected"


def test_notify_trade_rejected_notifies_both_teams():
    trade = _make_trade(team_a_id=201, team_b_id=202, status="REJECTED")
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_rejected(trade)
    notified_users = {c.kwargs["user_id"] for c in mock_send.call_args_list}
    assert notified_users == {201, 202}


def test_notify_trade_rejected_returns_sent_count():
    trade = _make_trade(team_a_id=1, team_b_id=2, status="REJECTED")
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email"):
        count = notify_trade_rejected(trade)
    assert count == 2


def test_notify_trade_rejected_context_includes_reason():
    trade = _make_trade(status="REJECTED", commissioner_comments="Too one-sided")
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_rejected(trade)
    for c in mock_send.call_args_list:
        ctx = c.kwargs["context"]
        assert ctx["rejection_reason"] == "Too one-sided"
        assert ctx["has_rejection_reason"] is True
        assert ctx["commissioner_comments"] == "Too one-sided"
        assert ctx["status"] == "REJECTED"


def test_notify_trade_rejected_no_comments_reason_is_none():
    """No commissioner comment → rejection_reason is None, has_rejection_reason is False."""
    trade = _make_trade(status="REJECTED", commissioner_comments=None)
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_rejected(trade)
    for c in mock_send.call_args_list:
        ctx = c.kwargs["context"]
        assert ctx["rejection_reason"] is None
        assert ctx["has_rejection_reason"] is False


def test_notify_trade_rejected_whitespace_only_comment_treated_as_none():
    """Whitespace-only comment → rejection_reason is None."""
    trade = _make_trade(status="REJECTED", commissioner_comments="   ")
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_rejected(trade)
    for c in mock_send.call_args_list:
        assert c.kwargs["context"]["rejection_reason"] is None
        assert c.kwargs["context"]["has_rejection_reason"] is False


def test_notify_trade_rejected_context_includes_league_and_trade_ids():
    trade = _make_trade(trade_id=55, league_id=7, status="REJECTED", commissioner_comments="No")
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_rejected(trade)
    for c in mock_send.call_args_list:
        assert c.kwargs["context"]["trade_id"] == 55
        assert c.kwargs["context"]["league_id"] == 7


# ─── notify_trade_submitted tests ─────────────────────────────────────────────

def setup_db():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return Session()


def test_notify_trade_submitted_uses_correct_template():
    db = setup_db()
    league = models.League(name="NotifLeague", current_season=2026)
    db.add(league)
    db.flush()
    team_a = models.User(username="ta", hashed_password="pw", league_id=league.id)
    team_b = models.User(username="tb", hashed_password="pw", league_id=league.id)
    commissioner = models.User(username="tc", hashed_password="pw", league_id=league.id, is_commissioner=True)
    db.add_all([team_a, team_b, commissioner])
    db.commit()
    for u in (team_a, team_b, commissioner):
        db.refresh(u)

    trade = models.Trade(league_id=league.id, team_a_id=team_a.id, team_b_id=team_b.id, status="PENDING")
    db.add(trade)
    db.commit()
    db.refresh(trade)

    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_submitted(db, trade, submitting_user_id=team_a.id)

    for c in mock_send.call_args_list:
        assert c.kwargs["template_id"] == "trade_submitted_pending_review"


def test_notify_trade_submitted_excludes_submitter():
    db = setup_db()
    league = models.League(name="NotifLeague2", current_season=2026)
    db.add(league)
    db.flush()
    team_a = models.User(username="ta2", hashed_password="pw", league_id=league.id)
    team_b = models.User(username="tb2", hashed_password="pw", league_id=league.id)
    commissioner = models.User(username="tc2", hashed_password="pw", league_id=league.id, is_commissioner=True)
    db.add_all([team_a, team_b, commissioner])
    db.commit()
    for u in (team_a, team_b, commissioner):
        db.refresh(u)

    trade = models.Trade(league_id=league.id, team_a_id=team_a.id, team_b_id=team_b.id, status="PENDING")
    db.add(trade)
    db.commit()
    db.refresh(trade)

    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_submitted(db, trade, submitting_user_id=team_a.id)

    notified = {c.kwargs["user_id"] for c in mock_send.call_args_list}
    assert team_a.id not in notified
    assert team_b.id in notified
    assert commissioner.id in notified


def test_notify_trade_submitted_returns_count():
    db = setup_db()
    league = models.League(name="NotifLeague3", current_season=2026)
    db.add(league)
    db.flush()
    team_a = models.User(username="ta3", hashed_password="pw", league_id=league.id)
    team_b = models.User(username="tb3", hashed_password="pw", league_id=league.id)
    commissioner = models.User(username="tc3", hashed_password="pw", league_id=league.id, is_commissioner=True)
    db.add_all([team_a, team_b, commissioner])
    db.commit()
    for u in (team_a, team_b, commissioner):
        db.refresh(u)

    trade = models.Trade(league_id=league.id, team_a_id=team_a.id, team_b_id=team_b.id, status="PENDING")
    db.add(trade)
    db.commit()
    db.refresh(trade)

    with patch.object(trade_notification_service.NotifyService, "send_transactional_email"):
        count = notify_trade_submitted(db, trade, submitting_user_id=team_a.id)

    # team_b + commissioner (team_a excluded as submitter)
    assert count == 2


def test_notify_trade_submitted_context_fields():
    db = setup_db()
    league = models.League(name="NotifLeague4", current_season=2026)
    db.add(league)
    db.flush()
    team_a = models.User(username="ta4", hashed_password="pw", league_id=league.id)
    team_b = models.User(username="tb4", hashed_password="pw", league_id=league.id)
    commissioner = models.User(username="tc4", hashed_password="pw", league_id=league.id, is_commissioner=True)
    db.add_all([team_a, team_b, commissioner])
    db.commit()
    for u in (team_a, team_b, commissioner):
        db.refresh(u)

    trade = models.Trade(league_id=league.id, team_a_id=team_a.id, team_b_id=team_b.id, status="PENDING")
    db.add(trade)
    db.commit()
    db.refresh(trade)

    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        notify_trade_submitted(db, trade, submitting_user_id=team_a.id)

    for c in mock_send.call_args_list:
        ctx = c.kwargs["context"]
        assert ctx["league_id"] == league.id
        assert ctx["trade_id"] == trade.id
        assert ctx["team_a_id"] == team_a.id
        assert ctx["team_b_id"] == team_b.id


# ─── Router integration: notification triggered after approve/reject ───────────

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


def _seed(api_db):
    league = models.League(name="NRouterLeague", current_season=2026)
    api_db.add(league)
    api_db.commit()
    api_db.refresh(league)

    api_db.add(models.LeagueSettings(league_id=league.id, roster_size=15))

    team_a = models.User(username=f"nra_{league.id}", hashed_password="pw", league_id=league.id, future_draft_budget=20)
    team_b = models.User(username=f"nrb_{league.id}", hashed_password="pw", league_id=league.id, future_draft_budget=20)
    commissioner = models.User(
        username=f"nrc_{league.id}", hashed_password="pw", league_id=league.id,
        is_commissioner=True, future_draft_budget=0,
    )
    api_db.add_all([team_a, team_b, commissioner])
    api_db.commit()
    for u in (team_a, team_b, commissioner):
        api_db.refresh(u)

    p_a = models.Player(name=f"NRP_A_{league.id}", position="RB", nfl_team="X")
    p_b = models.Player(name=f"NRP_B_{league.id}", position="WR", nfl_team="Y")
    api_db.add_all([p_a, p_b])
    api_db.commit()
    api_db.refresh(p_a)
    api_db.refresh(p_b)

    api_db.add(models.DraftPick(league_id=league.id, owner_id=team_a.id, player_id=p_a.id, year=2027))
    api_db.add(models.DraftPick(league_id=league.id, owner_id=team_b.id, player_id=p_b.id, year=2027))
    api_db.commit()

    return {"league": league, "team_a": team_a, "team_b": team_b,
            "commissioner": commissioner, "player_a": p_a, "player_b": p_b}


def _submit_trade(client, seeded):
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
    return resp.json()["trade_id"]


def test_router_approve_triggers_notify_trade_approved(client, api_db):
    """notify_trade_approved is called exactly once after a successful approval."""
    seeded = _seed(api_db)
    trade_id = _submit_trade(client, seeded)

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    with patch(
        "backend.routers.trades.notify_trade_approved"
    ) as mock_notify:
        resp = client.post(
            f"/trades/leagues/{seeded['league'].id}/{trade_id}/approve-v2",
            json={"commissioner_comments": "Approved!"},
        )
    assert resp.status_code == 200
    mock_notify.assert_called_once()
    trade_arg = mock_notify.call_args[0][0]
    assert trade_arg.status == "APPROVED"


def test_router_reject_triggers_notify_trade_rejected(client, api_db):
    """notify_trade_rejected is called exactly once after a rejection."""
    seeded = _seed(api_db)
    trade_id = _submit_trade(client, seeded)

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    with patch(
        "backend.routers.trades.notify_trade_rejected"
    ) as mock_notify:
        resp = client.post(
            f"/trades/leagues/{seeded['league'].id}/{trade_id}/reject-v2",
            json={"commissioner_comments": "Rejected for cause"},
        )
    assert resp.status_code == 200
    mock_notify.assert_called_once()
    trade_arg = mock_notify.call_args[0][0]
    assert trade_arg.status == "REJECTED"
    assert trade_arg.commissioner_comments == "Rejected for cause"


def test_router_approve_succeeds_even_if_notification_raises(client, api_db):
    """Notification failure must not roll back the approval — trade stays APPROVED."""
    seeded = _seed(api_db)
    trade_id = _submit_trade(client, seeded)

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    with patch(
        "backend.routers.trades.notify_trade_approved",
        side_effect=RuntimeError("SMTP down"),
    ):
        resp = client.post(
            f"/trades/leagues/{seeded['league'].id}/{trade_id}/approve-v2",
            json={"commissioner_comments": ""},
        )
    assert resp.status_code == 200
    assert resp.json()["trade"]["status"] == "APPROVED"


def test_router_reject_succeeds_even_if_notification_raises(client, api_db):
    """Notification failure must not roll back the rejection — trade stays REJECTED."""
    seeded = _seed(api_db)
    trade_id = _submit_trade(client, seeded)

    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]
    with patch(
        "backend.routers.trades.notify_trade_rejected",
        side_effect=RuntimeError("SMTP down"),
    ):
        resp = client.post(
            f"/trades/leagues/{seeded['league'].id}/{trade_id}/reject-v2",
            json={"commissioner_comments": "Rejected"},
        )
    assert resp.status_code == 200
    assert resp.json()["trade"]["status"] == "REJECTED"
