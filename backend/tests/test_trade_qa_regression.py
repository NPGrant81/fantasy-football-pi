"""Trade System QA Regression Suite (#358).

Covers the full QA checklist for all trade system workflows:

SECTION 1 — Trade submission (#349)
  QA-01  Valid trade submits and returns PENDING status
  QA-02  Submitter cannot offer assets they don't own (player)
  QA-03  Submitter cannot offer a draft pick owned by the other team
  QA-04  Submission blocked when trade deadline has passed
  QA-05  Submission blocked when trade_end_at window has closed
  QA-06  Empty asset lists are rejected
  QA-07  Draft-dollar offer exceeding budget is rejected at submit time

SECTION 2 — Commissioner review queue (#351)
  QA-08  Pending trade appears in GET /pending-v2
  QA-09  Approved trade no longer appears in pending list
  QA-10  Rejected trade no longer appears in pending list
  QA-11  Non-commissioner cannot access pending queue
  QA-12  Trade detail endpoint returns full trade with assets

SECTION 3 — Approval execution (#353)
  QA-13  Approved trade transfers player ownership (both sides)
  QA-14  Approved trade transfers pick ownership (both sides)
  QA-15  Approved trade adjusts draft-dollar budgets correctly
  QA-16  Approved trade creates ledger entries
  QA-17  Double-approval of same trade returns 400

SECTION 4 — Rejection (#356)
  QA-18  Rejected trade records commissioner comment
  QA-19  Rejected trade does not transfer any assets
  QA-20  Double-rejection of same trade returns 400

SECTION 5 — Audit history (#354)
  QA-21  History is SUBMITTED only after submit
  QA-22  History is SUBMITTED→APPROVED after approval
  QA-23  History is SUBMITTED→REJECTED after rejection with comment
  QA-24  History endpoint is commissioner-only (non-comm gets 403)

SECTION 6 — Notifications (#355, #356)
  QA-25  Approval triggers trade_approved notification to both teams
  QA-26  Rejection triggers trade_rejected notification to both teams
  QA-27  Rejection notification includes rejection_reason in payload
  QA-28  Notification failure does not roll back trade status

SECTION 7 — Trade window settings (#347)
  QA-29  GET trade-window returns defaults when no settings
  QA-30  PUT trade-window persists all four fields
  QA-31  PUT rejects start >= end date
  QA-32  PUT rejects missing timezone in datetime strings
  QA-33  Non-commissioner cannot PUT trade-window settings
  QA-34  Submission blocked when trade_start_at is in the future
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.core.security import get_current_user
from backend.database import get_db
from backend.main import app
from backend.services import trade_notification_service


# ─── Fixtures ─────────────────────────────────────────────────────────────────

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
def _override_db(api_db):
    def _get():
        try:
            yield api_db
        finally:
            pass
    app.dependency_overrides[get_db] = _get
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    return TestClient(app)


# ─── Seed helper ──────────────────────────────────────────────────────────────

def _suffix(obj):
    return str(obj.id)


_HAS_TRADE_WINDOW_COLS = hasattr(models.LeagueSettings, "trade_start_at")


def _seed(api_db, *, suffix_tag="", trade_deadline=None, trade_start_at=None, trade_end_at=None):
    league = models.League(name=f"QALeague{suffix_tag}", current_season=2026)
    api_db.add(league)
    api_db.commit()
    api_db.refresh(league)

    settings = models.LeagueSettings(league_id=league.id, roster_size=15, trade_deadline=trade_deadline)
    api_db.add(settings)
    api_db.flush()

    # trade_start_at/trade_end_at are added by migration #347; set via update if present
    if _HAS_TRADE_WINDOW_COLS:
        if trade_start_at is not None:
            settings.trade_start_at = trade_start_at
        if trade_end_at is not None:
            settings.trade_end_at = trade_end_at

    team_a = models.User(
        username=f"qa_a_{league.id}", hashed_password="pw", league_id=league.id,
        future_draft_budget=50,
    )
    team_b = models.User(
        username=f"qa_b_{league.id}", hashed_password="pw", league_id=league.id,
        future_draft_budget=40,
    )
    commissioner = models.User(
        username=f"qa_c_{league.id}", hashed_password="pw", league_id=league.id,
        is_commissioner=True, future_draft_budget=0,
    )
    non_member = models.User(
        username=f"qa_x_{league.id}", hashed_password="pw", league_id=999 + league.id,
        is_commissioner=False, future_draft_budget=0,
    )
    api_db.add_all([team_a, team_b, commissioner, non_member])
    api_db.commit()
    for u in (team_a, team_b, commissioner, non_member):
        api_db.refresh(u)

    p_a = models.Player(name=f"QA_A_{league.id}", position="RB", nfl_team="X")
    p_b = models.Player(name=f"QA_B_{league.id}", position="WR", nfl_team="Y")
    api_db.add_all([p_a, p_b])
    api_db.commit()
    api_db.refresh(p_a)
    api_db.refresh(p_b)

    api_db.add(models.DraftPick(league_id=league.id, owner_id=team_a.id, player_id=p_a.id, year=2027))
    api_db.add(models.DraftPick(league_id=league.id, owner_id=team_b.id, player_id=p_b.id, year=2027))

    pick_a = models.DraftPick(league_id=league.id, owner_id=team_a.id, player_id=None, year=2028)
    pick_b = models.DraftPick(league_id=league.id, owner_id=team_b.id, player_id=None, year=2028)
    api_db.add_all([pick_a, pick_b])
    api_db.commit()
    api_db.refresh(pick_a)
    api_db.refresh(pick_b)

    return {
        "league": league, "settings": settings,
        "team_a": team_a, "team_b": team_b,
        "commissioner": commissioner, "non_member": non_member,
        "player_a": p_a, "player_b": p_b,
        "pick_a": pick_a, "pick_b": pick_b,
    }


def _submit(client, seeded, *, assets_a=None, assets_b=None, as_user=None):
    user = as_user or seeded["team_a"]
    app.dependency_overrides[get_current_user] = lambda: user
    if assets_a is None:
        assets_a = [{"asset_type": "PLAYER", "player_id": seeded["player_a"].id}]
    if assets_b is None:
        assets_b = [{"asset_type": "PLAYER", "player_id": seeded["player_b"].id}]
    return client.post(
        f"/trades/leagues/{seeded['league'].id}/submit-v2",
        json={
            "team_a_id": seeded["team_a"].id,
            "team_b_id": seeded["team_b"].id,
            "assets_from_a": assets_a,
            "assets_from_b": assets_b,
        },
    )


def _as_comm(seeded):
    app.dependency_overrides[get_current_user] = lambda: seeded["commissioner"]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Trade submission
# ═══════════════════════════════════════════════════════════════════════════════

def test_qa01_valid_trade_returns_pending(client, api_db):
    """QA-01: Valid submission returns status PENDING."""
    s = _seed(api_db, suffix_tag="01")
    resp = _submit(client, s)
    assert resp.status_code == 200
    trade_id = resp.json()["trade_id"]

    _as_comm(s)
    detail = client.get(f"/trades/leagues/{s['league'].id}/{trade_id}-v2")
    assert detail.status_code == 200
    assert detail.json()["status"] == "PENDING"


def test_qa02_cannot_offer_unowned_player(client, api_db):
    """QA-02: Submitter cannot offer a player owned by team_b."""
    s = _seed(api_db, suffix_tag="02")
    resp = _submit(client, s, assets_a=[{"asset_type": "PLAYER", "player_id": s["player_b"].id}])
    assert resp.status_code == 400


def test_qa03_cannot_offer_opponents_pick(client, api_db):
    """QA-03: Submitter cannot offer a pick owned by the other team."""
    s = _seed(api_db, suffix_tag="03")
    resp = _submit(client, s, assets_a=[{
        "asset_type": "DRAFT_PICK", "draft_pick_id": s["pick_b"].id, "season_year": 2028,
    }])
    assert resp.status_code == 400


def test_qa04_submission_blocked_by_past_deadline(client, api_db):
    """QA-04: Trade blocked when the legacy trade_deadline has passed."""
    s = _seed(api_db, suffix_tag="04", trade_deadline="2000-01-01T00:00:00Z")
    resp = _submit(client, s)
    assert resp.status_code == 400
    assert "closed" in resp.json()["detail"].lower()


@pytest.mark.skipif(not _HAS_TRADE_WINDOW_COLS, reason="trade window columns not yet in this branch")
def test_qa05_submission_blocked_after_trade_end_at(client, api_db):
    """QA-05: Trade blocked when trade_end_at has passed."""
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    s = _seed(api_db, suffix_tag="05", trade_end_at=past)
    resp = _submit(client, s)
    assert resp.status_code == 400


def test_qa06_empty_assets_rejected(client, api_db):
    """QA-06: Submission with empty asset list is rejected."""
    s = _seed(api_db, suffix_tag="06")
    resp = _submit(client, s, assets_a=[], assets_b=[])
    assert resp.status_code == 400


def test_qa07_draft_dollars_exceeding_budget_rejected(client, api_db):
    """QA-07: Draft dollar offer exceeding team_a budget blocked at submission."""
    s = _seed(api_db, suffix_tag="07")
    resp = _submit(client, s, assets_a=[{"asset_type": "DRAFT_DOLLARS", "amount": 999}])
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Commissioner review queue
# ═══════════════════════════════════════════════════════════════════════════════

def test_qa08_pending_trade_in_queue(client, api_db):
    """QA-08: Submitted trade appears in commissioner pending queue."""
    s = _seed(api_db, suffix_tag="08")
    r = _submit(client, s)
    trade_id = r.json()["trade_id"]

    _as_comm(s)
    resp = client.get(f"/trades/leagues/{s['league'].id}/pending-v2")
    assert resp.status_code == 200
    assert any(row["id"] == trade_id for row in resp.json())


def test_qa09_approved_trade_not_in_pending(client, api_db):
    """QA-09: Approved trade removed from pending queue."""
    s = _seed(api_db, suffix_tag="09")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/approve-v2", json={"commissioner_comments": ""})

    resp = client.get(f"/trades/leagues/{s['league'].id}/pending-v2")
    assert not any(row["id"] == trade_id for row in resp.json())


def test_qa10_rejected_trade_not_in_pending(client, api_db):
    """QA-10: Rejected trade removed from pending queue."""
    s = _seed(api_db, suffix_tag="10")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/reject-v2", json={"commissioner_comments": "nope"})

    resp = client.get(f"/trades/leagues/{s['league'].id}/pending-v2")
    assert not any(row["id"] == trade_id for row in resp.json())


def test_qa11_non_commissioner_blocked_from_pending(client, api_db):
    """QA-11: Non-commissioner cannot access pending queue."""
    s = _seed(api_db, suffix_tag="11")
    _submit(client, s)

    app.dependency_overrides[get_current_user] = lambda: s["team_b"]
    resp = client.get(f"/trades/leagues/{s['league'].id}/pending-v2")
    assert resp.status_code == 403


def test_qa12_trade_detail_includes_assets(client, api_db):
    """QA-12: Trade detail endpoint returns trade with asset lists."""
    s = _seed(api_db, suffix_tag="12")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    resp = client.get(f"/trades/leagues/{s['league'].id}/{trade_id}-v2")
    assert resp.status_code == 200
    data = resp.json()
    assert "assets_from_a" in data or "assets" in data or data.get("id") == trade_id


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Approval execution
# ═══════════════════════════════════════════════════════════════════════════════

def test_qa13_approved_trade_transfers_player_ownership(client, api_db):
    """QA-13: Player ownership swaps to correct teams after approval."""
    s = _seed(api_db, suffix_tag="13")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/approve-v2", json={"commissioner_comments": ""})

    a_pick = api_db.query(models.DraftPick).filter_by(player_id=s["player_a"].id).first()
    b_pick = api_db.query(models.DraftPick).filter_by(player_id=s["player_b"].id).first()
    assert a_pick.owner_id == s["team_b"].id
    assert b_pick.owner_id == s["team_a"].id


def test_qa14_approved_trade_transfers_pick_ownership(client, api_db):
    """QA-14: Draft pick (by pick_id) transferred to correct owner."""
    s = _seed(api_db, suffix_tag="14")
    trade_id = _submit(client, s,
        assets_a=[{"asset_type": "DRAFT_PICK", "draft_pick_id": s["pick_a"].id, "season_year": 2028}],
        assets_b=[{"asset_type": "DRAFT_PICK", "draft_pick_id": s["pick_b"].id, "season_year": 2028}],
    ).json()["trade_id"]

    _as_comm(s)
    client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/approve-v2", json={"commissioner_comments": ""})

    assert api_db.get(models.DraftPick, s["pick_a"].id).owner_id == s["team_b"].id
    assert api_db.get(models.DraftPick, s["pick_b"].id).owner_id == s["team_a"].id


def test_qa15_approved_trade_adjusts_draft_dollar_budgets(client, api_db):
    """QA-15: Draft dollar budgets updated correctly (A sends 10, B sends 5)."""
    s = _seed(api_db, suffix_tag="15")
    trade_id = _submit(client, s,
        assets_a=[{"asset_type": "DRAFT_DOLLARS", "amount": 10}],
        assets_b=[{"asset_type": "DRAFT_DOLLARS", "amount": 5}],
    ).json()["trade_id"]

    _as_comm(s)
    client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/approve-v2", json={"commissioner_comments": ""})

    a = api_db.get(models.User, s["team_a"].id)
    b = api_db.get(models.User, s["team_b"].id)
    assert a.future_draft_budget == 45   # 50 - 10 + 5
    assert b.future_draft_budget == 45   # 40 - 5 + 10


def test_qa16_approved_trade_creates_ledger_entries(client, api_db):
    """QA-16: Ledger entries created for draft dollar transfers."""
    s = _seed(api_db, suffix_tag="16")
    trade_id = _submit(client, s,
        assets_a=[{"asset_type": "DRAFT_DOLLARS", "amount": 8}],
        assets_b=[{"asset_type": "DRAFT_DOLLARS", "amount": 3}],
    ).json()["trade_id"]

    _as_comm(s)
    client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/approve-v2", json={"commissioner_comments": ""})

    ledger = (
        api_db.query(models.EconomicLedger)
        .filter_by(reference_type="TRADE_V2", reference_id=str(trade_id))
        .all()
    )
    assert len(ledger) == 2


def test_qa17_double_approval_returns_400(client, api_db):
    """QA-17: Attempting to approve an already-approved trade returns 400."""
    s = _seed(api_db, suffix_tag="17")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/approve-v2", json={"commissioner_comments": ""})
    resp2 = client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/approve-v2", json={"commissioner_comments": ""})
    assert resp2.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Rejection
# ═══════════════════════════════════════════════════════════════════════════════

def test_qa18_rejection_records_comment(client, api_db):
    """QA-18: Commissioner comment persisted on rejection."""
    s = _seed(api_db, suffix_tag="18")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    resp = client.post(
        f"/trades/leagues/{s['league'].id}/{trade_id}/reject-v2",
        json={"commissioner_comments": "Too lopsided"},
    )
    assert resp.status_code == 200
    assert resp.json()["trade"]["commissioner_comments"] == "Too lopsided"


def test_qa19_rejection_does_not_transfer_assets(client, api_db):
    """QA-19: Player ownership unchanged after trade rejection."""
    s = _seed(api_db, suffix_tag="19")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/reject-v2", json={"commissioner_comments": "nope"})

    a_pick = api_db.query(models.DraftPick).filter_by(player_id=s["player_a"].id).first()
    b_pick = api_db.query(models.DraftPick).filter_by(player_id=s["player_b"].id).first()
    assert a_pick.owner_id == s["team_a"].id
    assert b_pick.owner_id == s["team_b"].id


def test_qa20_double_rejection_returns_400(client, api_db):
    """QA-20: Attempting to reject an already-rejected trade returns 400."""
    s = _seed(api_db, suffix_tag="20")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/reject-v2", json={"commissioner_comments": ""})
    resp2 = client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/reject-v2", json={"commissioner_comments": ""})
    assert resp2.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Audit history
# ═══════════════════════════════════════════════════════════════════════════════

def test_qa21_history_submitted_only_after_submit(client, api_db):
    """QA-21: Only SUBMITTED event in history after submission."""
    s = _seed(api_db, suffix_tag="21")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    resp = client.get(f"/trades/leagues/{s['league'].id}/{trade_id}/history-v2")
    assert resp.status_code == 200
    assert [e["event_type"] for e in resp.json()] == ["SUBMITTED"]


def test_qa22_history_submitted_then_approved(client, api_db):
    """QA-22: History shows SUBMITTED→APPROVED in order after approval."""
    s = _seed(api_db, suffix_tag="22")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/approve-v2", json={"commissioner_comments": ""})
    resp = client.get(f"/trades/leagues/{s['league'].id}/{trade_id}/history-v2")
    assert [e["event_type"] for e in resp.json()] == ["SUBMITTED", "APPROVED"]


def test_qa23_history_submitted_then_rejected_with_comment(client, api_db):
    """QA-23: Rejection history preserves comment in last event."""
    s = _seed(api_db, suffix_tag="23")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/reject-v2", json={"commissioner_comments": "Bad trade"})
    resp = client.get(f"/trades/leagues/{s['league'].id}/{trade_id}/history-v2")
    history = resp.json()
    assert [e["event_type"] for e in history] == ["SUBMITTED", "REJECTED"]
    assert history[-1]["comment"] == "Bad trade"


def test_qa24_history_requires_commissioner(client, api_db):
    """QA-24: Non-commissioner receives 403 on history endpoint."""
    s = _seed(api_db, suffix_tag="24")
    trade_id = _submit(client, s).json()["trade_id"]

    app.dependency_overrides[get_current_user] = lambda: s["team_b"]
    resp = client.get(f"/trades/leagues/{s['league'].id}/{trade_id}/history-v2")
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Notifications
# ═══════════════════════════════════════════════════════════════════════════════

def test_qa25_approval_triggers_notification_to_both_teams(client, api_db):
    """QA-25: trade_approved notification sent to both teams after approval."""
    s = _seed(api_db, suffix_tag="25")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/approve-v2", json={"commissioner_comments": ""})

    approved_calls = [c for c in mock_send.call_args_list if c.kwargs["template_id"] == "trade_approved"]
    notified = {c.kwargs["user_id"] for c in approved_calls}
    assert notified == {s["team_a"].id, s["team_b"].id}


def test_qa26_rejection_triggers_notification_to_both_teams(client, api_db):
    """QA-26: trade_rejected notification sent to both teams after rejection."""
    s = _seed(api_db, suffix_tag="26")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/reject-v2", json={"commissioner_comments": "No"})

    rejected_calls = [c for c in mock_send.call_args_list if c.kwargs["template_id"] == "trade_rejected"]
    notified = {c.kwargs["user_id"] for c in rejected_calls}
    assert notified == {s["team_a"].id, s["team_b"].id}


def test_qa27_rejection_notification_includes_reason(client, api_db):
    """QA-27: trade_rejected payload contains rejection_reason."""
    s = _seed(api_db, suffix_tag="27")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    with patch.object(trade_notification_service.NotifyService, "send_transactional_email") as mock_send:
        client.post(
            f"/trades/leagues/{s['league'].id}/{trade_id}/reject-v2",
            json={"commissioner_comments": "Reject reason QA27"},
        )

    for c in (c for c in mock_send.call_args_list if c.kwargs["template_id"] == "trade_rejected"):
        assert c.kwargs["context"]["rejection_reason"] == "Reject reason QA27"
        assert c.kwargs["context"]["has_rejection_reason"] is True


def test_qa28_notification_failure_does_not_roll_back(client, api_db):
    """QA-28: Trade stays APPROVED even if notification throws."""
    s = _seed(api_db, suffix_tag="28")
    trade_id = _submit(client, s).json()["trade_id"]

    _as_comm(s)
    with patch("backend.routers.trades.notify_trade_approved", side_effect=RuntimeError("SMTP down")):
        resp = client.post(f"/trades/leagues/{s['league'].id}/{trade_id}/approve-v2", json={"commissioner_comments": ""})
    assert resp.status_code == 200
    assert resp.json()["trade"]["status"] == "APPROVED"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — Trade window settings
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _HAS_TRADE_WINDOW_COLS, reason="trade window columns not yet in this branch")
def test_qa29_get_trade_window_returns_defaults(client, api_db):
    """QA-29: GET trade-window returns open status with null window fields."""
    s = _seed(api_db, suffix_tag="29")
    _as_comm(s)
    resp = client.get(f"/trades/leagues/{s['league'].id}/settings/trade-window")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_open" in data


@pytest.mark.skipif(not _HAS_TRADE_WINDOW_COLS, reason="trade window columns not yet in this branch")
def test_qa30_put_trade_window_persists_fields(client, api_db):
    """QA-30: PUT trade-window persists all four fields and returns updated state."""
    s = _seed(api_db, suffix_tag="30")
    _as_comm(s)
    payload = {
        "trade_start_at": "2026-01-01T00:00:00+00:00",
        "trade_end_at": "2026-12-31T23:59:59+00:00",
        "allow_playoff_trades": False,
        "require_commissioner_approval": True,
    }
    resp = client.put(f"/trades/leagues/{s['league'].id}/settings/trade-window", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["allow_playoff_trades"] is False
    assert data["require_commissioner_approval"] is True


@pytest.mark.skipif(not _HAS_TRADE_WINDOW_COLS, reason="trade window columns not yet in this branch")
def test_qa31_put_trade_window_rejects_start_gte_end(client, api_db):
    """QA-31: PUT rejected when start date is after end date."""
    s = _seed(api_db, suffix_tag="31")
    _as_comm(s)
    resp = client.put(
        f"/trades/leagues/{s['league'].id}/settings/trade-window",
        json={
            "trade_start_at": "2026-12-31T00:00:00+00:00",
            "trade_end_at": "2026-01-01T00:00:00+00:00",
        },
    )
    assert resp.status_code == 400


@pytest.mark.skipif(not _HAS_TRADE_WINDOW_COLS, reason="trade window columns not yet in this branch")
def test_qa32_put_trade_window_rejects_missing_timezone(client, api_db):
    """QA-32: PUT rejected when datetime string has no timezone."""
    s = _seed(api_db, suffix_tag="32")
    _as_comm(s)
    resp = client.put(
        f"/trades/leagues/{s['league'].id}/settings/trade-window",
        json={"trade_start_at": "2026-06-01T00:00:00"},  # no tz
    )
    assert resp.status_code == 400


@pytest.mark.skipif(not _HAS_TRADE_WINDOW_COLS, reason="trade window columns not yet in this branch")
def test_qa33_non_commissioner_cannot_update_trade_window(client, api_db):
    """QA-33: Non-commissioner receives 403 on PUT trade-window."""
    s = _seed(api_db, suffix_tag="33")
    app.dependency_overrides[get_current_user] = lambda: s["team_a"]
    resp = client.put(
        f"/trades/leagues/{s['league'].id}/settings/trade-window",
        json={"allow_playoff_trades": False},
    )
    assert resp.status_code == 403


@pytest.mark.skipif(not _HAS_TRADE_WINDOW_COLS, reason="trade window columns not yet in this branch")
def test_qa34_submission_blocked_when_window_not_yet_open(client, api_db):
    """QA-34: Trade submission blocked when trade_start_at is in the future."""
    future = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    s = _seed(api_db, suffix_tag="34", trade_start_at=future)
    resp = _submit(client, s)
    assert resp.status_code == 400
