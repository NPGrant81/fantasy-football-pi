from sqlalchemy.orm import Session
from .. import models
from datetime import datetime


def execute_trade(db: Session, trade_id: int, approver_id: int) -> models.TradeProposal:
    """Execute a pending trade proposal, swapping players and draft dollars.

    Only a commissioner should call this; caller check is done by router.
    """
    trade = db.query(models.TradeProposal).filter(models.TradeProposal.id == trade_id).first()
    if not trade:
        raise ValueError("Trade not found")
    if trade.status != "PENDING":
        raise ValueError("Trade not pending")

    # fetch involved users and picks
    from_user = db.query(models.User).filter(models.User.id == trade.from_user_id).first()
    to_user = db.query(models.User).filter(models.User.id == trade.to_user_id).first()
    if not from_user or not to_user:
        raise ValueError("Users involved in trade no longer exist")

    offered_pick = (
        db.query(models.DraftPick)
        .filter(models.DraftPick.owner_id == from_user.id, models.DraftPick.player_id == trade.offered_player_id)
        .first()
    )
    requested_pick = (
        db.query(models.DraftPick)
        .filter(models.DraftPick.owner_id == to_user.id, models.DraftPick.player_id == trade.requested_player_id)
        .first()
    )
    if not offered_pick or not requested_pick:
        raise ValueError("One of the offered/requested players is no longer on the proposed roster")

    # adjust budgets
    a_off = trade.offered_dollars or 0
    a_req = trade.requested_dollars or 0
    # ensure owners have enough (should be validated earlier, but double check)
    if from_user.future_draft_budget < a_off:
        raise ValueError("Proposer lacks sufficient future dollars")
    if to_user.future_draft_budget < a_req:
        raise ValueError("Target lacks sufficient future dollars")

    # cast to int so SQLite driver doesn't try to bind Decimal objects
    from_user.future_draft_budget = int(from_user.future_draft_budget + (a_req - a_off))
    to_user.future_draft_budget = int(to_user.future_draft_budget + (a_off - a_req))

    # swap player ownership
    offered_pick.owner_id = to_user.id
    requested_pick.owner_id = from_user.id

    trade.status = "APPROVED"
    trade.updated_at = datetime.utcnow().isoformat() if hasattr(trade, 'updated_at') else None

    # record transaction history
    from .transaction_service import log_transaction
    # offered player moved from from_user to to_user
    log_transaction(db, trade.league_id, trade.offered_player_id, from_user.id, to_user.id, "trade")
    # requested player moved opposite direction
    log_transaction(db, trade.league_id, trade.requested_player_id, to_user.id, from_user.id, "trade")

    # if either player was previously marked as a keeper, transfer ownership
    for pid, new_owner in [
        (trade.offered_player_id, to_user.id),
        (trade.requested_player_id, from_user.id),
    ]:
        k_entries = db.query(models.Keeper).filter(models.Keeper.player_id == pid).all()
        for k in k_entries:
            k.owner_id = new_owner

    db.commit()
    db.refresh(trade)
    return trade


def reject_trade(db: Session, trade_id: int, approver_id: int) -> models.TradeProposal:
    trade = db.query(models.TradeProposal).filter(models.TradeProposal.id == trade_id).first()
    if not trade:
        raise ValueError("Trade not found")
    if trade.status != "PENDING":
        raise ValueError("Trade not pending")
    trade.status = "REJECTED"
    trade.updated_at = datetime.utcnow().isoformat() if hasattr(trade, 'updated_at') else None
    db.commit()
    db.refresh(trade)
    return trade
