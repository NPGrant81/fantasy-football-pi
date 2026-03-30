import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.trades import (
    TradeReviewAction,
    approve_trade_v2,
    get_trade_history_v2,
    get_pending_trades_v2,
    reject_trade_v2,
    submit_trade_v2,
    TradeSubmissionCreate,
    TradeAssetCreate,
)
from fastapi import HTTPException


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return testing_session_local()


def make_league(db, name="ReviewLeague"):
    league = models.League(name=name, current_season=2026)
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def make_user(db, league, username, is_commissioner=False, budget=0):
    user = models.User(
        username=username,
        hashed_password="pw",
        league_id=league.id,
        is_commissioner=is_commissioner,
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


def make_pick(db, league_id, owner_id, player_id=None):
    pick = models.DraftPick(league_id=league_id, owner_id=owner_id, player_id=player_id, year=2027)
    db.add(pick)
    db.commit()
    db.refresh(pick)
    return pick


class CU:
    def __init__(self, user):
        self.id = user.id
        self.league_id = user.league_id
        self.is_superuser = bool(getattr(user, "is_superuser", False))


class SubmitCU:
    def __init__(self, user):
        self.id = user.id
        self.league_id = user.league_id
        self.future_draft_budget = user.future_draft_budget


def create_pending_trade(db):
    league = make_league(db)
    db.add(models.LeagueSettings(league_id=league.id, roster_size=16, trade_deadline=None))
    db.commit()

    team_a = make_user(db, league, "team-a", budget=20)
    team_b = make_user(db, league, "team-b", budget=15)
    commissioner = make_user(db, league, "comm", is_commissioner=True)

    player_a = make_player(db, "Player A", position="RB")
    player_b = make_player(db, "Player B", position="WR")
    make_pick(db, league.id, team_a.id, player_a.id)
    make_pick(db, league.id, team_b.id, player_b.id)

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[TradeAssetCreate(asset_type="PLAYER", player_id=player_a.id)],
        assets_from_b=[TradeAssetCreate(asset_type="PLAYER", player_id=player_b.id)],
    )
    created = submit_trade_v2(league.id, payload, db=db, current_user=SubmitCU(team_a))
    return league, commissioner, created["trade_id"]


def test_pending_trade_list_v2_returns_pending_trade():
    db = setup_db()
    league, commissioner, _ = create_pending_trade(db)

    rows = get_pending_trades_v2(league.id, db=db, current_user=CU(commissioner))
    assert len(rows) == 1
    assert rows[0]["status"] == "PENDING"
    assert rows[0]["assets_from_a"]
    assert rows[0]["assets_from_b"]


def test_approve_trade_v2_sets_status_and_comment():
    db = setup_db()
    league, commissioner, trade_id = create_pending_trade(db)

    result = approve_trade_v2(
        league.id,
        trade_id,
        TradeReviewAction(commissioner_comments="Looks good"),
        db=db,
        current_user=CU(commissioner),
    )

    assert result["message"] == "Trade approved"
    trade = db.get(models.Trade, trade_id)
    assert trade.status == "APPROVED"
    assert trade.commissioner_comments == "Looks good"
    assert trade.approved_at is not None

    events = get_trade_history_v2(league.id, trade_id, db=db, current_user=CU(commissioner))
    assert [row["event_type"] for row in events] == ["SUBMITTED", "APPROVED"]
    assert events[-1]["comment"] == "Looks good"


def test_reject_trade_v2_sets_status_and_comment():
    db = setup_db()
    league, commissioner, trade_id = create_pending_trade(db)

    result = reject_trade_v2(
        league.id,
        trade_id,
        TradeReviewAction(commissioner_comments="Insufficient value"),
        db=db,
        current_user=CU(commissioner),
    )

    assert result["message"] == "Trade rejected"
    trade = db.get(models.Trade, trade_id)
    assert trade.status == "REJECTED"
    assert trade.commissioner_comments == "Insufficient value"
    assert trade.rejected_at is not None

    events = get_trade_history_v2(league.id, trade_id, db=db, current_user=CU(commissioner))
    assert [row["event_type"] for row in events] == ["SUBMITTED", "REJECTED"]
    assert events[-1]["comment"] == "Insufficient value"


def test_review_v2_blocks_other_league_commissioner():
    db = setup_db()
    league, _, trade_id = create_pending_trade(db)

    other_league = make_league(db, name="OtherLeague")
    other_comm = make_user(db, other_league, "other-comm", is_commissioner=True)

    with pytest.raises(HTTPException) as exc:
        approve_trade_v2(
            league.id,
            trade_id,
            TradeReviewAction(commissioner_comments=None),
            db=db,
            current_user=CU(other_comm),
        )

    assert exc.value.status_code == 403


def test_trade_history_v2_blocks_other_league_commissioner():
    db = setup_db()
    league, _, trade_id = create_pending_trade(db)

    other_league = make_league(db, name="HistoryOtherLeague")
    other_comm = make_user(db, other_league, "history-other-comm", is_commissioner=True)

    with pytest.raises(HTTPException) as exc:
        get_trade_history_v2(league.id, trade_id, db=db, current_user=CU(other_comm))

    assert exc.value.status_code == 403


def test_approve_trade_v2_executes_assets_and_ledger():
    db = setup_db()
    league = make_league(db, name="ExecutionLeague")
    db.add(models.LeagueSettings(league_id=league.id, roster_size=16, trade_deadline=None))
    db.commit()

    team_a = make_user(db, league, "a-owner", budget=25)
    team_b = make_user(db, league, "b-owner", budget=30)
    commissioner = make_user(db, league, "exec-comm", is_commissioner=True)

    player_a = make_player(db, "Exec A", position="RB")
    player_b = make_player(db, "Exec B", position="WR")

    make_pick(db, league.id, team_a.id, player_a.id)
    make_pick(db, league.id, team_b.id, player_b.id)
    pick_a_extra = make_pick(db, league.id, team_a.id, None)

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[
            TradeAssetCreate(asset_type="PLAYER", player_id=player_a.id),
            TradeAssetCreate(asset_type="DRAFT_PICK", draft_pick_id=pick_a_extra.id, season_year=2027),
            TradeAssetCreate(asset_type="DRAFT_DOLLARS", amount=6),
        ],
        assets_from_b=[
            TradeAssetCreate(asset_type="PLAYER", player_id=player_b.id),
            TradeAssetCreate(asset_type="DRAFT_DOLLARS", amount=2),
        ],
    )
    created = submit_trade_v2(league.id, payload, db=db, current_user=SubmitCU(team_a))
    trade_id = created["trade_id"]

    approve_trade_v2(
        league.id,
        trade_id,
        TradeReviewAction(commissioner_comments="Execute trade"),
        db=db,
        current_user=CU(commissioner),
    )

    updated_trade = db.get(models.Trade, trade_id)
    assert updated_trade.status == "APPROVED"

    a_player_pick = (
        db.query(models.DraftPick)
        .filter(models.DraftPick.league_id == league.id, models.DraftPick.player_id == player_a.id)
        .first()
    )
    b_player_pick = (
        db.query(models.DraftPick)
        .filter(models.DraftPick.league_id == league.id, models.DraftPick.player_id == player_b.id)
        .first()
    )
    moved_extra_pick = db.get(models.DraftPick, pick_a_extra.id)

    assert a_player_pick.owner_id == team_b.id
    assert b_player_pick.owner_id == team_a.id
    assert moved_extra_pick.owner_id == team_b.id

    refreshed_a = db.get(models.User, team_a.id)
    refreshed_b = db.get(models.User, team_b.id)
    # A offered 6, received 2 => net -4 ; B net +4
    assert refreshed_a.future_draft_budget == 21
    assert refreshed_b.future_draft_budget == 34

    ledger_rows = (
        db.query(models.EconomicLedger)
        .filter(
            models.EconomicLedger.reference_type == "TRADE_V2",
            models.EconomicLedger.reference_id == str(trade_id),
        )
        .all()
    )
    assert len(ledger_rows) == 2


def test_approve_trade_v2_rolls_back_on_invalid_player_ownership():
    db = setup_db()
    league, commissioner, trade_id = create_pending_trade(db)

    trade = db.get(models.Trade, trade_id)
    player_asset = next(asset for asset in trade.assets if asset.asset_type == "PLAYER" and asset.asset_side == "A")
    owner_row = db.get(models.User, trade.team_a_id)
    wrong_owner_id = (
        db.query(models.User.id)
        .filter(models.User.league_id == league.id, models.User.id != trade.team_a_id)
        .first()[0]
    )
    owned_pick = (
        db.query(models.DraftPick)
        .filter(
            models.DraftPick.league_id == league.id,
            models.DraftPick.owner_id == trade.team_a_id,
            models.DraftPick.player_id == player_asset.player_id,
        )
        .first()
    )
    owned_pick.owner_id = wrong_owner_id
    db.commit()

    with pytest.raises(HTTPException) as exc:
        approve_trade_v2(
            league.id,
            trade_id,
            TradeReviewAction(commissioner_comments="should fail"),
            db=db,
            current_user=CU(commissioner),
        )

    assert exc.value.status_code == 400
    unchanged_trade = db.get(models.Trade, trade_id)
    assert unchanged_trade.status == "PENDING"
    # budget unchanged due to rollback
    refreshed_owner = db.get(models.User, owner_row.id)
    assert refreshed_owner.future_draft_budget == owner_row.future_draft_budget
