"""Unit tests for trade_execution_service.execute_trade_v2_approval (#353).

Covers:
- Happy path: players, draft picks, and draft dollars transferred atomically
- Rollback on team-A player no longer owned
- Rollback on team-B player no longer owned
- Rollback on team-A draft pick no longer owned
- Rollback on team-B draft pick no longer owned
- Rollback when team-A has insufficient draft dollars
- Rollback when team-B has insufficient draft dollars
- Correct ledger entries created for draft-dollar transfers
- ValueError on trade not found
- ValueError on already-approved trade
- Multi-asset trade (players + picks + dollars both sides)
- APPROVED event recorded after successful execution
- Trade timestamps set correctly
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.services.trade_execution_service import execute_trade_v2_approval


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return session()


def make_league(db, name="ExecLeague"):
    league = models.League(name=name, current_season=2026)
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def make_user(db, league, username, budget=100):
    user = models.User(
        username=username,
        hashed_password="pw",
        league_id=league.id,
        future_draft_budget=budget,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_player(db, name, position="RB"):
    player = models.Player(name=name, position=position, nfl_team="AAA")
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def make_pick(db, league_id, owner_id, player_id=None, year=2027):
    pick = models.DraftPick(league_id=league_id, owner_id=owner_id, player_id=player_id, year=year)
    db.add(pick)
    db.commit()
    db.refresh(pick)
    return pick


def create_pending_trade(db, league, team_a, team_b, assets_a, assets_b):
    """Create a Trade row with PENDING status and the given assets."""
    trade = models.Trade(
        league_id=league.id,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        status="PENDING",
    )
    db.add(trade)
    db.flush()

    for asset in assets_a:
        db.add(models.TradeAsset(trade_id=trade.id, asset_side="A", **asset))
    for asset in assets_b:
        db.add(models.TradeAsset(trade_id=trade.id, asset_side="B", **asset))

    db.commit()
    db.refresh(trade)
    return trade


# ─── Happy path tests ─────────────────────────────────────────────────────────

def test_execute_player_swap_transfers_ownership():
    """Players are moved to correct owners after approval."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=0)
    team_b = make_user(db, league, "b", budget=0)
    commissioner = make_user(db, league, "comm", budget=0)

    p_a = make_player(db, "PA")
    p_b = make_player(db, "PB")
    make_pick(db, league.id, team_a.id, p_a.id)
    make_pick(db, league.id, team_b.id, p_b.id)

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "PLAYER", "player_id": p_a.id}],
        assets_b=[{"asset_type": "PLAYER", "player_id": p_b.id}],
    )

    execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    a_pick = db.query(models.DraftPick).filter_by(player_id=p_a.id).first()
    b_pick = db.query(models.DraftPick).filter_by(player_id=p_b.id).first()
    assert a_pick.owner_id == team_b.id
    assert b_pick.owner_id == team_a.id


def test_execute_draft_pick_swap_transfers_ownership():
    """Draft picks (by pick ID) are transferred to the other team."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=0)
    team_b = make_user(db, league, "b", budget=0)
    commissioner = make_user(db, league, "comm", budget=0)

    pick_a = make_pick(db, league.id, team_a.id, year=2028)
    pick_b = make_pick(db, league.id, team_b.id, year=2028)

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "DRAFT_PICK", "draft_pick_id": pick_a.id, "season_year": 2028}],
        assets_b=[{"asset_type": "DRAFT_PICK", "draft_pick_id": pick_b.id, "season_year": 2028}],
    )

    execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    assert db.get(models.DraftPick, pick_a.id).owner_id == team_b.id
    assert db.get(models.DraftPick, pick_b.id).owner_id == team_a.id


def test_execute_draft_dollars_updates_budgets_and_creates_ledger_entries():
    """Draft dollar transfer adjusts budgets and creates ledger entries."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=50)
    team_b = make_user(db, league, "b", budget=30)
    commissioner = make_user(db, league, "comm", budget=0)

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "DRAFT_DOLLARS", "amount": 10}],
        assets_b=[{"asset_type": "DRAFT_DOLLARS", "amount": 5}],
    )

    execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    a = db.get(models.User, team_a.id)
    b = db.get(models.User, team_b.id)
    # A sent 10, received 5 → net -5 from 50 = 45
    assert a.future_draft_budget == 45
    # B sent 5, received 10 → net +5 from 30 = 35
    assert b.future_draft_budget == 35

    ledger = (
        db.query(models.EconomicLedger)
        .filter(
            models.EconomicLedger.reference_type == "TRADE_V2",
            models.EconomicLedger.reference_id == str(trade.id),
        )
        .all()
    )
    assert len(ledger) == 2


def test_execute_multi_asset_trade_all_transfers_atomic():
    """Multi-asset trade: player + pick + dollars all transfer correctly."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=40)
    team_b = make_user(db, league, "b", budget=20)
    commissioner = make_user(db, league, "comm", budget=0)

    p_a = make_player(db, "PA")
    p_b = make_player(db, "PB")
    make_pick(db, league.id, team_a.id, p_a.id)
    make_pick(db, league.id, team_b.id, p_b.id)
    extra_pick_a = make_pick(db, league.id, team_a.id, year=2029)

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[
            {"asset_type": "PLAYER", "player_id": p_a.id},
            {"asset_type": "DRAFT_PICK", "draft_pick_id": extra_pick_a.id, "season_year": 2029},
            {"asset_type": "DRAFT_DOLLARS", "amount": 8},
        ],
        assets_b=[
            {"asset_type": "PLAYER", "player_id": p_b.id},
            {"asset_type": "DRAFT_DOLLARS", "amount": 3},
        ],
    )

    execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    assert db.query(models.DraftPick).filter_by(player_id=p_a.id).first().owner_id == team_b.id
    assert db.query(models.DraftPick).filter_by(player_id=p_b.id).first().owner_id == team_a.id
    assert db.get(models.DraftPick, extra_pick_a.id).owner_id == team_b.id
    assert db.get(models.User, team_a.id).future_draft_budget == 35   # 40 - 8 + 3
    assert db.get(models.User, team_b.id).future_draft_budget == 25   # 20 - 3 + 8


def test_execute_sets_approved_status_and_timestamp():
    """Trade status becomes APPROVED and approved_at is set."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=0)
    team_b = make_user(db, league, "b", budget=0)
    commissioner = make_user(db, league, "comm", budget=0)

    p_a = make_player(db, "PA")
    p_b = make_player(db, "PB")
    make_pick(db, league.id, team_a.id, p_a.id)
    make_pick(db, league.id, team_b.id, p_b.id)

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "PLAYER", "player_id": p_a.id}],
        assets_b=[{"asset_type": "PLAYER", "player_id": p_b.id}],
    )

    result = execute_trade_v2_approval(
        db, trade_id=trade.id, approver_id=commissioner.id, commissioner_comments="All good"
    )

    assert result.status == "APPROVED"
    assert result.approved_at is not None
    assert result.commissioner_comments == "All good"


def test_execute_records_approved_event():
    """An APPROVED TradeEvent is persisted after successful execution."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=0)
    team_b = make_user(db, league, "b", budget=0)
    commissioner = make_user(db, league, "comm", budget=0)

    p_a = make_player(db, "PA")
    p_b = make_player(db, "PB")
    make_pick(db, league.id, team_a.id, p_a.id)
    make_pick(db, league.id, team_b.id, p_b.id)

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "PLAYER", "player_id": p_a.id}],
        assets_b=[{"asset_type": "PLAYER", "player_id": p_b.id}],
    )

    execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    events = db.query(models.TradeEvent).filter_by(trade_id=trade.id).all()
    event_types = [e.event_type for e in events]
    assert "APPROVED" in event_types
    approved_event = next(e for e in events if e.event_type == "APPROVED")
    assert approved_event.actor_user_id == commissioner.id


# ─── Error and rollback tests ─────────────────────────────────────────────────

def test_execute_raises_on_trade_not_found():
    """ValueError raised when trade_id doesn't exist."""
    db = setup_db()
    with pytest.raises(ValueError, match="not found"):
        execute_trade_v2_approval(db, trade_id=9999, approver_id=1)


def test_execute_raises_on_non_pending_trade():
    """ValueError raised when trade is not PENDING."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a")
    team_b = make_user(db, league, "b")

    trade = models.Trade(league_id=league.id, team_a_id=team_a.id, team_b_id=team_b.id, status="APPROVED")
    db.add(trade)
    db.commit()
    db.refresh(trade)

    with pytest.raises(ValueError, match="[Pp]ending"):
        execute_trade_v2_approval(db, trade_id=trade.id, approver_id=team_a.id)


def test_execute_rolls_back_when_team_a_player_not_owned():
    """Rollback: player offered by team A no longer owned — trade stays PENDING."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=0)
    team_b = make_user(db, league, "b", budget=0)
    commissioner = make_user(db, league, "comm", budget=0)

    p_a = make_player(db, "PA")
    p_b = make_player(db, "PB")
    # p_a is NOT in a DraftPick row owned by team_a
    make_pick(db, league.id, team_b.id, p_b.id)

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "PLAYER", "player_id": p_a.id}],
        assets_b=[{"asset_type": "PLAYER", "player_id": p_b.id}],
    )

    with pytest.raises(ValueError, match="[Tt]eam A"):
        execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    # Trade must remain PENDING after rollback
    db.expire_all()
    assert db.get(models.Trade, trade.id).status == "PENDING"
    # Team B's pick should still belong to team_b
    assert db.query(models.DraftPick).filter_by(player_id=p_b.id).first().owner_id == team_b.id


def test_execute_rolls_back_when_team_b_player_not_owned():
    """Rollback: player requested from team B no longer owned."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=0)
    team_b = make_user(db, league, "b", budget=0)
    commissioner = make_user(db, league, "comm", budget=0)

    p_a = make_player(db, "PA")
    p_b = make_player(db, "PB")
    make_pick(db, league.id, team_a.id, p_a.id)
    # p_b is owned by team_a, NOT team_b — simulates post-submission ownership change

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "PLAYER", "player_id": p_a.id}],
        assets_b=[{"asset_type": "PLAYER", "player_id": p_b.id}],
    )

    with pytest.raises(ValueError, match="[Tt]eam B"):
        execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    db.expire_all()
    assert db.get(models.Trade, trade.id).status == "PENDING"
    # Team A's player pick should be unchanged
    assert db.query(models.DraftPick).filter_by(player_id=p_a.id).first().owner_id == team_a.id


def test_execute_rolls_back_when_team_a_pick_not_owned():
    """Rollback: draft pick offered by team A no longer belongs to team A."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=0)
    team_b = make_user(db, league, "b", budget=0)
    commissioner = make_user(db, league, "comm", budget=0)

    p_b = make_player(db, "PB")
    make_pick(db, league.id, team_b.id, p_b.id)
    # Pick created owned by team_b, not team_a
    pick = make_pick(db, league.id, team_b.id, year=2028)

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "DRAFT_PICK", "draft_pick_id": pick.id, "season_year": 2028}],
        assets_b=[{"asset_type": "PLAYER", "player_id": p_b.id}],
    )

    with pytest.raises(ValueError, match="[Tt]eam A"):
        execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    db.expire_all()
    assert db.get(models.Trade, trade.id).status == "PENDING"


def test_execute_rolls_back_when_team_b_pick_not_owned():
    """Rollback: draft pick offered by team B no longer belongs to team B."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=0)
    team_b = make_user(db, league, "b", budget=0)
    commissioner = make_user(db, league, "comm", budget=0)

    p_a = make_player(db, "PA")
    make_pick(db, league.id, team_a.id, p_a.id)
    # Pick created owned by team_a, not team_b
    pick = make_pick(db, league.id, team_a.id, year=2028)

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "PLAYER", "player_id": p_a.id}],
        assets_b=[{"asset_type": "DRAFT_PICK", "draft_pick_id": pick.id, "season_year": 2028}],
    )

    with pytest.raises(ValueError, match="[Tt]eam B"):
        execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    db.expire_all()
    assert db.get(models.Trade, trade.id).status == "PENDING"


def test_execute_rolls_back_when_team_a_lacks_draft_dollars():
    """Rollback: team A can't cover the draft dollar amount they offered."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=5)   # Only 5 available
    team_b = make_user(db, league, "b", budget=50)
    commissioner = make_user(db, league, "comm", budget=0)

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "DRAFT_DOLLARS", "amount": 20}],   # Requesting to send 20
        assets_b=[{"asset_type": "DRAFT_DOLLARS", "amount": 1}],
    )

    with pytest.raises(ValueError, match="[Tt]eam A"):
        execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    db.expire_all()
    assert db.get(models.User, team_a.id).future_draft_budget == 5
    assert db.get(models.User, team_b.id).future_draft_budget == 50
    assert db.get(models.Trade, trade.id).status == "PENDING"


def test_execute_rolls_back_when_team_b_lacks_draft_dollars():
    """Rollback: team B can't cover their dollar offer."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=50)
    team_b = make_user(db, league, "b", budget=3)   # Only 3 available
    commissioner = make_user(db, league, "comm", budget=0)

    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "DRAFT_DOLLARS", "amount": 5}],
        assets_b=[{"asset_type": "DRAFT_DOLLARS", "amount": 10}],  # Requesting to send 10
    )

    with pytest.raises(ValueError, match="[Tt]eam B"):
        execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    db.expire_all()
    assert db.get(models.User, team_a.id).future_draft_budget == 50
    assert db.get(models.User, team_b.id).future_draft_budget == 3
    assert db.get(models.Trade, trade.id).status == "PENDING"


def test_execute_dollars_only_no_ledger_when_zero():
    """No ledger entry is created when a team's dollar contribution is zero."""
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "a", budget=30)
    team_b = make_user(db, league, "b", budget=0)
    commissioner = make_user(db, league, "comm", budget=0)

    p_a = make_player(db, "PA")
    p_b = make_player(db, "PB")
    make_pick(db, league.id, team_a.id, p_a.id)
    make_pick(db, league.id, team_b.id, p_b.id)

    # Only team_a offers dollars; team_b offers a player
    trade = create_pending_trade(
        db, league, team_a, team_b,
        assets_a=[{"asset_type": "DRAFT_DOLLARS", "amount": 10}],
        assets_b=[{"asset_type": "PLAYER", "player_id": p_b.id}],
    )

    execute_trade_v2_approval(db, trade_id=trade.id, approver_id=commissioner.id)

    ledger = (
        db.query(models.EconomicLedger)
        .filter_by(reference_type="TRADE_V2", reference_id=str(trade.id))
        .all()
    )
    # Only one ledger row (team_a → team_b), not two
    assert len(ledger) == 1
    assert ledger[0].from_owner_id == team_a.id
    assert ledger[0].to_owner_id == team_b.id
    assert db.get(models.User, team_a.id).future_draft_budget == 20
