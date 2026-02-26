from sqlalchemy.orm import Session
from datetime import datetime

from .. import models


def log_transaction(
    db: Session,
    league_id: int,
    player_id: int,
    old_owner_id: int | None,
    new_owner_id: int | None,
    transaction_type: str,
    notes: str | None = None,
) -> models.TransactionHistory:
    """Record a change in ownership or related event.

    transaction_type should be one of:
    'draft', 'trade', 'waiver_add', 'waiver_drop', 'drop', etc.
    """
    th = models.TransactionHistory(
        league_id=league_id,
        player_id=player_id,
        old_owner_id=old_owner_id,
        new_owner_id=new_owner_id,
        transaction_type=transaction_type,
        notes=notes,
    )
    db.add(th)
    db.flush()
    return th


def get_owner_at_time(db: Session, player_id: int, target_date: datetime) -> int | None:
    """Return the owner_id for the given player on or before the timestamp.

    If no matching record exists, returns None.
    """
    txn = (
        db.query(models.TransactionHistory)
        .filter(
            models.TransactionHistory.player_id == player_id,
            models.TransactionHistory.timestamp <= target_date,
        )
        .order_by(models.TransactionHistory.timestamp.desc())
        .first()
    )
    return txn.new_owner_id if txn else None


def get_acquisition_method(db: Session, player_id: int, owner_id: int) -> str | None:
    """Return the first transaction_type that brought the player to this owner.
    """
    txn = (
        db.query(models.TransactionHistory)
        .filter(
            models.TransactionHistory.player_id == player_id,
            models.TransactionHistory.new_owner_id == owner_id,
        )
        .order_by(models.TransactionHistory.timestamp)
        .first()
    )
    if not txn:
        return None
    # map our internal types to simple labels
    if txn.transaction_type == "draft":
        return "DRAFT"
    if txn.transaction_type == "trade":
        return "TRADE"
    if txn.transaction_type in ("waiver_add", "waiver_drop"):
        return "WAIVER"
    return txn.transaction_type.upper()
