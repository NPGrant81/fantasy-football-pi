from datetime import datetime
from sqlalchemy.orm import Session
from .. import models
from .transaction_service import get_owner_at_time, get_acquisition_method, log_transaction


def compute_keeper_flags(
    db: Session,
    league_id: int,
    player_id: int,
    owner_id: int,
    rule: models.KeeperRules,
) -> dict:
    """Return a dictionary of boolean flags that indicate potential policy violations.

    Used when an owner selects a player as a keeper; values are written to
    the Keeper.flag_* columns and also may be surfaced to the UI.
    """
    flags = {"flag_waiver": False, "flag_trade": False, "flag_drop": False}

    # waiver wire rule
    if rule.waiver_policy:
        # flag if the owner ever picked the player up via waiver
        wtxn = (
            db.query(models.TransactionHistory)
            .filter(
                models.TransactionHistory.player_id == player_id,
                models.TransactionHistory.transaction_type == "waiver_add",
                models.TransactionHistory.new_owner_id == owner_id,
            )
            .first()
        )
        if wtxn:
            flags["flag_waiver"] = True

    # trade deadline rule
    if rule.trade_deadline:
        owner_at_deadline = get_owner_at_time(db, player_id, rule.trade_deadline)
        if owner_at_deadline != owner_id:
            flags["flag_trade"] = True

    # drafted‑only rule: ensure player never left roster (i.e. owner never dropped it)
    if rule.drafted_only:
        t = (
            db.query(models.TransactionHistory)
            .filter(
                models.TransactionHistory.player_id == player_id,
                models.TransactionHistory.transaction_type.in_(["drop","waiver_drop"]),
                models.TransactionHistory.old_owner_id == owner_id,
            )
            .first()
        )
        if t:
            flags["flag_drop"] = True

    return flags


def get_effective_budget(db: Session, owner_id: int) -> int:
    """Return the current draft budget after locked keepers have been deducted."""
    owner = db.query(models.User).filter(models.User.id == owner_id).first()
    if not owner or not owner.league_id:
        return 0
    settings = (
        db.query(models.LeagueSettings)
        .filter(models.LeagueSettings.league_id == owner.league_id)
        .first()
    )
    if not settings:
        return 0
    total_budget = settings.starting_waiver_budget or 0
    used = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.owner_id == owner_id,
            models.Keeper.status == "locked",
        )
        .with_entities(models.Keeper.keep_cost)
        .all()
    )
    used_sum = sum([u[0] for u in used])
    return total_budget - used_sum


def project_budget(db: Session, owner_id: int) -> int:
    """Return projected budget including pending keepers (not yet locked)."""
    base = get_effective_budget(db, owner_id)
    pending = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.owner_id == owner_id,
            models.Keeper.status == "pending",
        )
        .with_entities(models.Keeper.keep_cost)
        .all()
    )
    return base - sum([p[0] for p in pending])


def lock_keepers_for_league(db: Session, league_id: int, season: int):
    """Move all pending keepers across a league to locked and apply budget deductions.

    This would be run when the keeper deadline passes. It returns the number of
    records updated.
    """
    pending = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.league_id == league_id,
            models.Keeper.season == season,
            models.Keeper.status == "pending",
        )
    )
    count = pending.update({"status": "locked"}, synchronize_session="fetch")
    db.commit()
    return count
