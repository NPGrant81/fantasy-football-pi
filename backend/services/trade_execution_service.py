from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from .. import models
from .ledger_service import record_ledger_entry
from .trade_event_service import record_trade_event
from .transaction_service import log_transaction


def _assets_by_side(trade: models.Trade):
    side_a = [asset for asset in trade.assets if asset.asset_side == "A"]
    side_b = [asset for asset in trade.assets if asset.asset_side == "B"]
    return side_a, side_b


def _find_player_pick(db: Session, *, league_id: int, owner_id: int, player_id: int):
    return (
        db.query(models.DraftPick)
        .filter(
            models.DraftPick.league_id == league_id,
            models.DraftPick.owner_id == owner_id,
            models.DraftPick.player_id == player_id,
        )
        .first()
    )


def _draft_dollars_to_int(value: object) -> int:
    return int(round(float(value or 0)))


def execute_trade_v2_approval(
    db: Session,
    *,
    trade_id: int,
    approver_id: int,
    commissioner_comments: str | None = None,
) -> models.Trade:
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        raise ValueError("Trade not found")
    if trade.status != "PENDING":
        raise ValueError("Only pending trades can be approved")

    team_a = db.query(models.User).filter(models.User.id == trade.team_a_id).first()
    team_b = db.query(models.User).filter(models.User.id == trade.team_b_id).first()
    if not team_a or not team_b:
        raise ValueError("One or more teams on this trade no longer exist")

    side_a, side_b = _assets_by_side(trade)

    try:
        # 1) Move player ownership via DraftPick records.
        for asset in side_a:
            if asset.asset_type != "PLAYER" or asset.player_id is None:
                continue
            offered_pick = _find_player_pick(
                db,
                league_id=trade.league_id,
                owner_id=trade.team_a_id,
                player_id=asset.player_id,
            )
            if not offered_pick:
                raise ValueError(f"Team A no longer owns player_id={asset.player_id}")
            offered_pick.owner_id = trade.team_b_id
            log_transaction(
                db,
                trade.league_id,
                int(asset.player_id),
                trade.team_a_id,
                trade.team_b_id,
                "trade",
                notes=f"trade_v2:{trade.id}",
            )

        for asset in side_b:
            if asset.asset_type != "PLAYER" or asset.player_id is None:
                continue
            requested_pick = _find_player_pick(
                db,
                league_id=trade.league_id,
                owner_id=trade.team_b_id,
                player_id=asset.player_id,
            )
            if not requested_pick:
                raise ValueError(f"Team B no longer owns player_id={asset.player_id}")
            requested_pick.owner_id = trade.team_a_id
            log_transaction(
                db,
                trade.league_id,
                int(asset.player_id),
                trade.team_b_id,
                trade.team_a_id,
                "trade",
                notes=f"trade_v2:{trade.id}",
            )

        # 2) Move draft pick ownership by pick id.
        for asset in side_a:
            if asset.asset_type != "DRAFT_PICK" or asset.draft_pick_id is None:
                continue
            pick = db.query(models.DraftPick).filter(models.DraftPick.id == asset.draft_pick_id).first()
            if not pick or pick.league_id != trade.league_id:
                raise ValueError(f"Draft pick {asset.draft_pick_id} was not found in this league")
            if pick.owner_id != trade.team_a_id:
                raise ValueError(f"Team A does not own draft_pick_id={asset.draft_pick_id}")
            pick.owner_id = trade.team_b_id

        for asset in side_b:
            if asset.asset_type != "DRAFT_PICK" or asset.draft_pick_id is None:
                continue
            pick = db.query(models.DraftPick).filter(models.DraftPick.id == asset.draft_pick_id).first()
            if not pick or pick.league_id != trade.league_id:
                raise ValueError(f"Draft pick {asset.draft_pick_id} was not found in this league")
            if pick.owner_id != trade.team_b_id:
                raise ValueError(f"Team B does not own draft_pick_id={asset.draft_pick_id}")
            pick.owner_id = trade.team_a_id

        # 3) Apply draft-dollar transfers and ledger entries.
        offered_by_a = sum(
            _draft_dollars_to_int(asset.amount)
            for asset in side_a
            if asset.asset_type == "DRAFT_DOLLARS"
        )
        offered_by_b = sum(
            _draft_dollars_to_int(asset.amount)
            for asset in side_b
            if asset.asset_type == "DRAFT_DOLLARS"
        )

        if int(team_a.future_draft_budget or 0) < offered_by_a:
            raise ValueError("Team A lacks sufficient draft dollars")
        if int(team_b.future_draft_budget or 0) < offered_by_b:
            raise ValueError("Team B lacks sufficient draft dollars")

        team_a.future_draft_budget = int(team_a.future_draft_budget or 0) - offered_by_a + offered_by_b
        team_b.future_draft_budget = int(team_b.future_draft_budget or 0) - offered_by_b + offered_by_a

        if offered_by_a > 0:
            record_ledger_entry(
                db,
                league_id=trade.league_id,
                season_year=None,
                currency_type="DRAFT_DOLLARS",
                amount=offered_by_a,
                from_owner_id=trade.team_a_id,
                to_owner_id=trade.team_b_id,
                transaction_type="TRADE_DOLLARS",
                reference_type="TRADE_V2",
                reference_id=str(trade.id),
                notes="team A offered draft dollars",
                created_by_user_id=approver_id,
            )

        if offered_by_b > 0:
            record_ledger_entry(
                db,
                league_id=trade.league_id,
                season_year=None,
                currency_type="DRAFT_DOLLARS",
            amount=offered_by_b,
                from_owner_id=trade.team_b_id,
                to_owner_id=trade.team_a_id,
                transaction_type="TRADE_DOLLARS",
                reference_type="TRADE_V2",
                reference_id=str(trade.id),
                notes="team B offered draft dollars",
                created_by_user_id=approver_id,
            )

        # 4) Mark trade approved.
        trade.status = "APPROVED"
        trade.approved_at = datetime.now(UTC)
        trade.commissioner_comments = (commissioner_comments or "").strip() or None

        record_trade_event(
            db,
            trade_id=trade.id,
            event_type="APPROVED",
            actor_user_id=approver_id,
            comment=trade.commissioner_comments,
        )

        db.commit()
        db.refresh(trade)
        return trade
    except Exception:
        db.rollback()
        raise
