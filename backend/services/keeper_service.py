from datetime import UTC, datetime
from sqlalchemy.orm import Session
from .. import models
from .transaction_service import get_owner_at_time, get_acquisition_method, log_transaction
from .ledger_service import record_ledger_entry


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

    if rule is None:
        return flags

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
    """Return the current draft budget after locked keepers have been deducted.

    Historically this deducted from the league settings starting_waiver_budget,
    but draft budgets now live on the user as `future_draft_budget`.  We still
    include the old calculation for backwards compatibility in tests when the
    column is absent (sqlite in‑memory), but the canonical value is stored on
    the user record and is permanently decremented when keepers are locked.
    """
    owner = db.query(models.User).filter(models.User.id == owner_id).first()
    if not owner or not owner.league_id:
        return 0

    # prefer the explicit future_draft_budget column if it exists
    if hasattr(owner, "future_draft_budget"):
        return int(owner.future_draft_budget or 0)

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


def compute_surplus_recommendations(db: Session, owner_id: int, season: int) -> list[dict]:
    """Return list of keeper candidates marked with `recommended` flag.

    Surplus value = projected auction value (current season) - keep_cost.  The
    list is sorted descending by surplus and truncated to the league's
    ``max_keepers`` setting, also filtering out players who have already been
    kept a maximum number of years.
    """
    owner = db.query(models.User).filter(models.User.id == owner_id).first()
    if not owner or not owner.league_id:
        return []
    rules = (
        db.query(models.KeeperRules)
        .filter(models.KeeperRules.league_id == owner.league_id)
        .first()
    )
    limit = rules.max_keepers if rules else None
    max_years = rules.max_years_per_player if rules else None

    # fetch all pending or locked keepers for this owner to compute cost
    keepers = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.owner_id == owner_id,
            models.Keeper.season == season,
        )
        .all()
    )
    # we want roster players - so we need to query owner roster (via transactions?)
    # for simplicity assume `DraftPick` or roster table exists; to keep this self-contained
    # we'll just treat keeper entries themselves as the candidate set for now.

    # fetch projection values
    from .projection_service import get_projected_auction_value

    candidates = []
    for k in keepers:
        proj = get_projected_auction_value(db, k.player_id, season)
        surplus = (proj or 0) - float(k.keep_cost)
        candidates.append({
            "player_id": k.player_id,
            "surplus": surplus,
            "years_kept_count": k.years_kept_count,
            "keep_cost": k.keep_cost,
            "projected_value": proj,
        })
    # filter by max_years
    if max_years is not None:
        candidates = [c for c in candidates if c["years_kept_count"] < max_years]
    candidates.sort(key=lambda x: x["surplus"], reverse=True)
    if limit is not None:
        candidates = candidates[:limit]
    for c in candidates:
        c["recommended"] = True
    return candidates


def veto_keepers(db: Session, owner_id: int, league_id: int, season: int):
    """Un‑approve and unlock an owner's keeper selections."""
    ks = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.owner_id == owner_id,
            models.Keeper.league_id == league_id,
            models.Keeper.season == season,
            models.Keeper.status == "locked",
        )
        .all()
    )
    for k in ks:
        k.status = "pending"
        k.locked_at = None
        k.approved_by_commish = False
    db.commit()
    return len(ks)


def reset_keepers(db: Session, league_id: int, season: int, owner_id: int | None = None):
    """Clear keeper selections for an owner or entire league."""
    qry = db.query(models.Keeper).filter(
        models.Keeper.league_id == league_id,
        models.Keeper.season == season,
    )
    if owner_id:
        qry = qry.filter(models.Keeper.owner_id == owner_id)
    count = qry.delete(synchronize_session="fetch")
    db.commit()
    return count


# --- notification helpers --------------------------------------------------
from ..services.notifications import NotifyService


def send_window_open_notifications(db: Session, league_id: int):
    """Email all owners that the keeper window has opened."""
    users = db.query(models.User).filter(models.User.league_id == league_id).all()
    for u in users:
        NotifyService.send_transactional_email(
            user_id=u.id,
            template_id="keeper_window_open",
            context={"league_id": league_id},
        )


def send_deadline_reminder(db: Session, league_id: int):
    """Send 24‑hour reminder to owners."""
    users = db.query(models.User).filter(models.User.league_id == league_id).all()
    for u in users:
        NotifyService.send_transactional_email(
            user_id=u.id,
            template_id="keeper_deadline_reminder",
            context={"league_id": league_id},
        )


def send_veto_alert(db: Session, owner_id: int, league_id: int):
    """Inform a single owner that their keeper list was un‑approved."""
    NotifyService.send_transactional_email(
        user_id=owner_id,
        template_id="keeper_veto_alert",
        context={"league_id": league_id},
    )


def lock_keepers_for_league(db: Session, league_id: int, season: int):
    """Move all pending keepers across a league to locked and apply budget deductions.

    This would be run when the keeper deadline passes or when the commissioner
    explicitly finalizes lists.  It:
      * sets status to "locked"
      * stamps locked_at with now
      * increments years_kept_count for repeat keepers
      * deducts the keep_cost from each owner.future_draft_budget

    Returns the number of records updated.
    """
    keepers = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.league_id == league_id,
            models.Keeper.season == season,
            models.Keeper.status == "pending",
        )
        .all()
    )
    now = datetime.now(UTC)
    owner_updates: dict[int, int] = {}  # owner_id -> total cost
    for k in keepers:
        k.status = "locked"
        k.locked_at = now
        # bump years_kept_count for existing entries (kept previous year)
        k.years_kept_count = (k.years_kept_count or 0) + 1
        owner_updates.setdefault(k.owner_id, 0)
        owner_updates[k.owner_id] += int(k.keep_cost)
    # apply budget deductions
    for owner_id, cost in owner_updates.items():
        owner = db.query(models.User).filter(models.User.id == owner_id).first()
        if owner and hasattr(owner, "future_draft_budget"):
            owner.future_draft_budget = int((owner.future_draft_budget or 0) - cost)
            record_ledger_entry(
                db,
                league_id=league_id,
                season_year=season,
                currency_type="DRAFT_DOLLARS",
                amount=cost,
                from_owner_id=owner_id,
                to_owner_id=None,
                transaction_type="KEEPER_LOCK",
                reference_type="LEAGUE_KEEPER_LOCK",
                reference_id=f"{league_id}:{season}:{owner_id}",
                notes="keeper lock budget deduction",
            )
    db.commit()
    return len(keepers)
