from datetime import UTC, datetime
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import func

from ..database import get_db
from .. import models
from ..core.security import get_current_user, get_current_active_admin
from ..services import keeper_service
from ..services.player_service import normalize_display_name as _normalize_player_name
from ..services.ledger_service import record_ledger_entry
from ..services.league_position_service import (
    get_active_positions_for_league,
    normalize_player_position,
)
from ..services.validation_service import (
    validate_keeper_settings_boundary,
    validate_keeper_settings_dynamic_rules,
)

router = APIRouter(
    prefix="/keepers",
    tags=["Keepers"]
)

# --- Schemas for owner-facing endpoints ---
class KeeperSelectionSchema(BaseModel):
    player_id: int
    keep_cost: float
    years_kept_count: Optional[int] = None
    status: str
    approved_by_commish: bool

class RecommendedSchema(BaseModel):
    player_id: int
    surplus: float
    projected_value: Optional[float] = None
    keep_cost: float
    years_kept_count: Optional[int] = None
    recommended: bool

class AvailablePlayerSchema(BaseModel):
    player_id: int
    name: str
    position: str
    nfl_team: Optional[str] = None
    draft_price: int
    is_selected: bool
    is_eligible: bool
    reason_ineligible: Optional[str] = None
    years_kept_count: int = 0

class KeeperPageResponse(BaseModel):
    owner_id: int
    owner_name: str
    selections: List[KeeperSelectionSchema]
    recommended: List[RecommendedSchema]
    available_players: List[AvailablePlayerSchema]
    selected_count: int
    max_allowed: int
    estimated_budget: int
    effective_budget: int
    ineligible: List[int] = []

class SubmitKeepersRequest(BaseModel):
    players: List[KeeperSelectionSchema]


class KeeperOverrideRequest(BaseModel):
    owner_id: int
    player_name: str
    nfl_team: str
    season: Optional[int] = None
    gsis_id: Optional[str] = None
    keep_cost: float = 0
    years_kept_count: int = 1


class KeeperImportRowResult(BaseModel):
    row_number: int
    status: str
    detail: str


class KeeperImportResult(BaseModel):
    dry_run: bool
    processed: int
    inserted: int
    updated: int
    skipped: int
    errors: List[KeeperImportRowResult]


class EconomicImportResult(BaseModel):
    dry_run: bool
    processed: int
    inserted: int
    updated: int
    skipped: int
    errors: List[KeeperImportRowResult]


VALID_ECON_ENTRY_TYPES = {
    "STARTING_BUDGET",
    "TRADE",
    "AWARD",
}

MIN_VALID_SEASON_YEAR = 2000
MAX_VALID_SEASON_YEAR = datetime.now(UTC).year + 2


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _validate_season_year(season: int, *, label: str = "season") -> int:
    normalized = int(season)
    if normalized < MIN_VALID_SEASON_YEAR or normalized > MAX_VALID_SEASON_YEAR:
        raise HTTPException(
            status_code=400,
            detail=f"{label} must be between {MIN_VALID_SEASON_YEAR} and {MAX_VALID_SEASON_YEAR}",
        )
    return normalized


def _rollover_prior_season_keepers(db: Session, league_id: int, current_season: int) -> None:
    # When season advances, freeze any stale pending selections from prior seasons.
    stale_pending = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.league_id == league_id,
            models.Keeper.season < current_season,
            models.Keeper.status == "pending",
        )
        .all()
    )
    if not stale_pending:
        return

    now = _utc_now()
    for keeper in stale_pending:
        keeper.status = "locked"
        if keeper.locked_at is None:
            keeper.locked_at = now
    db.commit()


def _current_keeper_season(db: Session, league_id: int) -> int:
    if not league_id:
        raise HTTPException(status_code=400, detail="User not in a league")
    settings = (
        db.query(models.LeagueSettings)
        .filter(models.LeagueSettings.league_id == league_id)
        .first()
    )
    # Default to current year when league draft year has not been configured yet.
    season = settings.draft_year if settings and settings.draft_year is not None else _utc_now().year
    normalized_season = _validate_season_year(int(season))
    _rollover_prior_season_keepers(db, league_id, normalized_season)
    return normalized_season


def _resolve_owner_for_import(
    db: Session,
    league_id: int,
    owner_username: Optional[str],
    owner_team_name: Optional[str],
) -> Optional[models.User]:
    owner_username = (owner_username or "").strip()
    owner_team_name = (owner_team_name or "").strip()

    if owner_username:
        owner = (
            db.query(models.User)
            .filter(
                models.User.league_id == league_id,
                func.lower(models.User.username) == owner_username.lower(),
            )
            .first()
        )
        if owner:
            return owner

    if owner_team_name:
        owner = (
            db.query(models.User)
            .filter(
                models.User.league_id == league_id,
                func.lower(models.User.team_name) == owner_team_name.lower(),
            )
            .first()
        )
        if owner:
            return owner

    return None


def _resolve_player_for_import(
    db: Session,
    player_name: str,
    nfl_team: str,
    gsis_id: Optional[str],
) -> Optional[models.Player]:
    normalized_gsis = (gsis_id or "").strip()
    if normalized_gsis:
        by_gsis = (
            db.query(models.Player)
            .filter(models.Player.gsis_id == normalized_gsis)
            .first()
        )
        if by_gsis:
            return by_gsis

    normalized_name = (player_name or "").strip()
    normalized_team = (nfl_team or "").strip()
    if not normalized_name or not normalized_team:
        return None

    candidates = (
        db.query(models.Player)
        .filter(
            func.lower(models.Player.name) == normalized_name.lower(),
            func.lower(models.Player.nfl_team) == normalized_team.lower(),
        )
        .all()
    )
    if not candidates:
        return None

    # If multiple candidates exist, prefer one with gsis_id set.
    with_gsis = [p for p in candidates if p.gsis_id]
    if len(with_gsis) == 1:
        return with_gsis[0]
    return candidates[0]

# --- Owner routes ---
@router.get("/", response_model=KeeperPageResponse)
def get_my_keepers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Return keeper page data for the logged-in owner."""
    if not current_user.league_id:
        raise HTTPException(status_code=400, detail="User not in a league")
    season = _current_keeper_season(db, current_user.league_id)

    # fetch existing selections
    keepers = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.owner_id == current_user.id,
            models.Keeper.season == season,
        )
        .all()
    )
    selections = [KeeperSelectionSchema(
        player_id=k.player_id,
        keep_cost=float(k.keep_cost),
        years_kept_count=k.years_kept_count,
        status=k.status,
        approved_by_commish=k.approved_by_commish,
    ) for k in keepers]

    recs = keeper_service.compute_surplus_recommendations(db, current_user.id, season)
    recommended = [RecommendedSchema(**r) for r in recs]

    rules = db.query(models.KeeperRules).filter(models.KeeperRules.league_id == current_user.league_id).first()
    max_allowed = rules.max_keepers if rules else 3
    max_years = rules.max_years_per_player if rules else 1
    
    ineligible_ids: list[int] = []
    if rules and rules.max_years_per_player is not None:
        # any player whose years_kept_count >= max should be flagged
        limit = rules.max_years_per_player
        ineligible_ids = [k.player_id for k in keepers if k.years_kept_count >= limit]

    # Build set of selected player IDs for quick lookup
    selected_player_ids = {k.player_id for k in keepers}
    
    # Build dict of keeper info by player_id for eligibility checking
    keeper_by_player_id = {k.player_id: k for k in keepers}
    active_positions = set(get_active_positions_for_league(db, current_user.league_id))
    
    # Fetch draft picks (the pool of available players to keep)
    draft_picks = (
        db.query(models.DraftPick)
        .options(selectinload(models.DraftPick.player))
        .filter(
            models.DraftPick.owner_id == current_user.id,
            models.DraftPick.league_id == current_user.league_id,
        )
        .all()
    )
    
    # Build available players list
    available_players = []
    for pick in draft_picks:
        if not pick.player:
            continue
        player_position = normalize_player_position(pick.player.position)
        if player_position not in active_positions:
            continue
        
        is_selected = pick.player_id in selected_player_ids
        keeper_info = keeper_by_player_id.get(pick.player_id)
        years_kept = keeper_info.years_kept_count if keeper_info else 0
        
        # Determine eligibility
        is_eligible = True
        reason_ineligible = None
        
        if max_years is not None and years_kept > 0 and years_kept >= max_years:
            is_eligible = False
            reason_ineligible = f"Already designated as keeper for {years_kept} year(s); max allowed is {max_years}"
        
        available_players.append(AvailablePlayerSchema(
            player_id=pick.player_id,
            name=_normalize_player_name(pick.player.name),
            position=player_position,
            nfl_team=pick.player.nfl_team,
            draft_price=int(pick.amount),
            is_selected=is_selected,
            is_eligible=is_eligible,
            reason_ineligible=reason_ineligible,
            years_kept_count=years_kept,
        ))
    
    # Sort: selected first, then eligible, then ineligible
    available_players.sort(key=lambda p: (not p.is_selected, not p.is_eligible))

    return KeeperPageResponse(
        owner_id=current_user.id,
        owner_name=current_user.team_name or current_user.username,
        selections=selections,
        recommended=recommended,
        available_players=available_players,
        selected_count=len(selections),
        max_allowed=max_allowed,
        estimated_budget=keeper_service.project_budget(db, current_user.id),
        effective_budget=keeper_service.get_effective_budget(db, current_user.id),
        ineligible=ineligible_ids,
    )

@router.post("/")
def save_my_keepers(
    request: SubmitKeepersRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Replace the owner's pending keeper selections. Does not lock."""
    if not current_user.league_id:
        raise HTTPException(status_code=400, detail="User not in a league")
    season = _current_keeper_season(db, current_user.league_id)

    # commissioner overrides always win; owner saves cannot remove/replace them.
    override_player_ids = {
        row.player_id
        for row in db.query(models.Keeper)
        .filter(
            models.Keeper.owner_id == current_user.id,
            models.Keeper.league_id == current_user.league_id,
            models.Keeper.season == season,
            models.Keeper.status == "commish_override",
        )
        .all()
    }

    # simple: delete existing pending entries for owner and add new ones
    db.query(models.Keeper).filter(
        models.Keeper.owner_id == current_user.id,
        models.Keeper.season == season,
        models.Keeper.status == "pending",
    ).delete(synchronize_session="fetch")

    active_positions = set(get_active_positions_for_league(db, current_user.league_id))
    player_ids = [
        p.player_id
        for p in request.players
        if p.player_id not in override_player_ids
    ]
    players_by_id = {
        player.id: player
        for player in db.query(models.Player)
        .filter(models.Player.id.in_(player_ids))
        .all()
    }

    for p in request.players:
        if p.player_id in override_player_ids:
            continue
        player = players_by_id.get(p.player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Keeper player not found.")
        if normalize_player_position(player.position) not in active_positions:
            raise HTTPException(
                status_code=400,
                detail=f"Position {player.position} is disabled for this league.",
            )
        k = models.Keeper(
            league_id=current_user.league_id,
            owner_id=current_user.id,
            player_id=p.player_id,
            season=season,
            keep_cost=p.keep_cost,
            status="pending",
        )
        # compute flags
        rule = db.query(models.KeeperRules).filter(models.KeeperRules.league_id == current_user.league_id).first()
        flags = keeper_service.compute_keeper_flags(db, current_user.league_id, p.player_id, current_user.id, rule)
        k.flag_waiver = flags.get("flag_waiver", False)
        k.flag_trade = flags.get("flag_trade", False)
        k.flag_drop = flags.get("flag_drop", False)
        db.add(k)
    db.commit()
    return {"status": "success", "count": len(request.players)}

@router.post("/lock")
def lock_my_keepers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Lock the current pending list for the owner."""
    if not current_user.league_id:
        raise HTTPException(status_code=400, detail="User not in a league")
    season = _current_keeper_season(db, current_user.league_id)

    # check lock date
    rules = db.query(models.KeeperRules).filter(models.KeeperRules.league_id == current_user.league_id).first()
    if rules and rules.deadline_date:
        now = _utc_now()
        deadline = rules.deadline_date
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        if deadline < now:
            raise HTTPException(status_code=400, detail="Keeper window has closed")

    # update pending for this owner only
    lock_time = _utc_now()
    count = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.owner_id == current_user.id,
            models.Keeper.season == season,
            models.Keeper.status == "pending",
        )
        .update({"status": "locked", "locked_at": lock_time}, synchronize_session="fetch")
    )
    # reload owner record from the DB to ensure it's attached to session
    owner = db.get(models.User, current_user.id)
    pending = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.owner_id == current_user.id,
            models.Keeper.season == season,
            models.Keeper.status == "locked",
        )
        .with_entities(models.Keeper.keep_cost)
        .all()
    )
    total_cost = sum([p[0] for p in pending])
    if owner is not None and hasattr(owner, "future_draft_budget"):
        owner.future_draft_budget = int((owner.future_draft_budget or 0) - total_cost)
    db.commit()
    return {"status": "locked", "count": count}

@router.delete("/{player_id}")
def remove_keeper(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Remove a pending player from owner's list."""
    season = _current_keeper_season(db, current_user.league_id)
    db.query(models.Keeper).filter(
        models.Keeper.owner_id == current_user.id,
        models.Keeper.season == season,
        models.Keeper.player_id == player_id,
        models.Keeper.status == "pending",
    ).delete()
    db.commit()
    return {"status": "removed"}

# --- Commissioner/admin endpoints ---

class OwnerKeepersOut(BaseModel):
    owner_id: int
    username: Optional[str]
    selections: List[KeeperSelectionSchema]

@router.get("/admin", response_model=List[OwnerKeepersOut])
def list_all_keepers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_admin),
):
    """Return all owners' keeper lists to the commissioner."""
    if not current_user.is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Commissioner required")
    season = _current_keeper_season(db, current_user.league_id)
    all_keepers = db.query(models.Keeper).filter(models.Keeper.league_id == current_user.league_id, models.Keeper.season == season).all()
    result: dict[int, OwnerKeepersOut] = {}
    for k in all_keepers:
        entry = result.setdefault(k.owner_id, OwnerKeepersOut(owner_id=k.owner_id, username=k.owner.username if k.owner else None, selections=[]))
        entry.selections.append(KeeperSelectionSchema(
            player_id=k.player_id,
            keep_cost=float(k.keep_cost),
            years_kept_count=k.years_kept_count,
            status=k.status,
            approved_by_commish=k.approved_by_commish,
        ))
    return list(result.values())

@router.post("/admin/{owner_id}/veto")
def veto_owner_list(
    owner_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_admin),
):
    if not current_user.is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Commissioner required")
    season = _current_keeper_season(db, current_user.league_id)
    count = keeper_service.veto_keepers(db, owner_id, current_user.league_id, season)
    return {"vetoed": count}

@router.post("/admin/reset")
def reset_league_keepers(
    owner_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_admin),
):
    if not current_user.is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Commissioner required")
    season = _current_keeper_season(db, current_user.league_id)
    count = keeper_service.reset_keepers(db, current_user.league_id, season, owner_id)
    return {"cleared": count}


@router.post("/admin/override")
def commissioner_override_keeper(
    request: KeeperOverrideRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_admin),
):
    if not current_user.is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Commissioner required")

    owner = (
        db.query(models.User)
        .filter(
            models.User.id == request.owner_id,
            models.User.league_id == current_user.league_id,
        )
        .first()
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found in this league")

    season = _validate_season_year(int(request.season), label="request.season") if request.season is not None else _current_keeper_season(db, current_user.league_id)
    player = _resolve_player_for_import(
        db,
        player_name=request.player_name,
        nfl_team=request.nfl_team,
        gsis_id=request.gsis_id,
    )
    if not player:
        raise HTTPException(status_code=404, detail="Player not found by gsis_id or name/team")

    existing = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.owner_id == owner.id,
            models.Keeper.league_id == current_user.league_id,
            models.Keeper.season == season,
            models.Keeper.player_id == player.id,
        )
        .first()
    )

    if existing:
        lock_time = _utc_now()
        existing.keep_cost = request.keep_cost
        existing.years_kept_count = max(0, int(request.years_kept_count or 0))
        existing.status = "commish_override"
        existing.approved_by_commish = True
        existing.locked_at = lock_time
    else:
        lock_time = _utc_now()
        db.add(
            models.Keeper(
                league_id=current_user.league_id,
                owner_id=owner.id,
                player_id=player.id,
                season=season,
                keep_cost=request.keep_cost,
                years_kept_count=max(0, int(request.years_kept_count or 0)),
                approved_by_commish=True,
                status="commish_override",
                locked_at=lock_time,
            )
        )

    db.commit()
    return {
        "status": "override_applied",
        "owner_id": owner.id,
        "player_id": player.id,
        "season": season,
    }


@router.get("/admin/history-template", response_class=PlainTextResponse)
def download_keeper_history_template(
    current_user: models.User = Depends(get_current_active_admin),
):
    if not current_user.is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Commissioner required")

    return (
        "season,owner_username,owner_team_name,player_name,nfl_team,gsis_id,keep_cost,years_kept_count,status\n"
        "2025,alice,Team Alice,Justin Jefferson,MIN,00-0036322,25,2,historical_import\n"
    )


@router.get("/admin/economic-history-template", response_class=PlainTextResponse)
def download_economic_history_template(
    current_user: models.User = Depends(get_current_active_admin),
):
    if not current_user.is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Commissioner required")

    return (
        "season,entry_type,owner_username,owner_team_name,from_owner_username,to_owner_username,amount,currency_type,note,reference_id\n"
        "2025,STARTING_BUDGET,alice,Team Alice,,,200,DRAFT_DOLLARS,Initial auction budget,budget-2025-alice\n"
        "2025,TRADE,,,alice,bob,15,DRAFT_DOLLARS,Preseason pick swap,trade-2025-alice-bob-1\n"
        "2025,AWARD,bob,Team Bob,,,10,DRAFT_DOLLARS,Compensatory bonus,award-2025-bob\n"
    )


@router.post("/admin/import-history", response_model=KeeperImportResult)
async def import_keeper_history_csv(
    file: UploadFile = File(...),
    dry_run: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_admin),
):
    if not current_user.is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Commissioner required")

    payload = await file.read()
    try:
        decoded = payload.decode("utf-8-sig")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to decode CSV: {exc}")

    reader = csv.DictReader(io.StringIO(decoded))
    required_cols = {
        "season",
        "owner_username",
        "owner_team_name",
        "player_name",
        "nfl_team",
        "gsis_id",
        "keep_cost",
        "years_kept_count",
        "status",
    }
    found_cols = set(reader.fieldnames or [])
    if not required_cols.issubset(found_cols):
        missing = sorted(required_cols - found_cols)
        raise HTTPException(status_code=400, detail=f"CSV missing required columns: {', '.join(missing)}")

    inserted = 0
    updated = 0
    skipped = 0
    errors: List[KeeperImportRowResult] = []

    for idx, row in enumerate(reader, start=2):
        season_raw = (row.get("season") or "").strip()
        player_name = (row.get("player_name") or "").strip()
        nfl_team = (row.get("nfl_team") or "").strip()
        gsis_id = (row.get("gsis_id") or "").strip() or None
        owner_username = (row.get("owner_username") or "").strip()
        owner_team_name = (row.get("owner_team_name") or "").strip()
        status_val = (row.get("status") or "historical_import").strip() or "historical_import"

        if not season_raw.isdigit():
            skipped += 1
            errors.append(KeeperImportRowResult(row_number=idx, status="skipped", detail="invalid season"))
            continue
        season = _validate_season_year(int(season_raw))

        owner = _resolve_owner_for_import(
            db,
            league_id=current_user.league_id,
            owner_username=owner_username,
            owner_team_name=owner_team_name,
        )
        if not owner:
            skipped += 1
            errors.append(KeeperImportRowResult(row_number=idx, status="skipped", detail="owner not found"))
            continue

        player = _resolve_player_for_import(db, player_name=player_name, nfl_team=nfl_team, gsis_id=gsis_id)
        if not player:
            skipped += 1
            errors.append(KeeperImportRowResult(row_number=idx, status="skipped", detail="player not found"))
            continue

        try:
            keep_cost = float(row.get("keep_cost") or 0)
        except ValueError:
            keep_cost = 0
        try:
            years_kept_count = int(float(row.get("years_kept_count") or 0))
        except ValueError:
            years_kept_count = 0

        existing = (
            db.query(models.Keeper)
            .filter(
                models.Keeper.league_id == current_user.league_id,
                models.Keeper.owner_id == owner.id,
                models.Keeper.player_id == player.id,
                models.Keeper.season == season,
            )
            .first()
        )

        if existing:
            existing.keep_cost = keep_cost
            existing.years_kept_count = max(0, years_kept_count)
            existing.status = status_val
            existing.approved_by_commish = True
            updated += 1
        else:
            db.add(
                models.Keeper(
                    league_id=current_user.league_id,
                    owner_id=owner.id,
                    player_id=player.id,
                    season=season,
                    keep_cost=keep_cost,
                    years_kept_count=max(0, years_kept_count),
                    approved_by_commish=True,
                    status=status_val,
                )
            )
            inserted += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return KeeperImportResult(
        dry_run=dry_run,
        processed=inserted + updated + skipped,
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )


@router.post("/admin/import-economic-history", response_model=EconomicImportResult)
async def import_economic_history_csv(
    file: UploadFile = File(...),
    dry_run: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_admin),
):
    if not current_user.is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Commissioner required")

    payload = await file.read()
    try:
        decoded = payload.decode("utf-8-sig")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to decode CSV: {exc}")

    reader = csv.DictReader(io.StringIO(decoded))
    required_cols = {
        "season",
        "entry_type",
        "owner_username",
        "owner_team_name",
        "from_owner_username",
        "to_owner_username",
        "amount",
        "currency_type",
        "note",
        "reference_id",
    }
    found_cols = set(reader.fieldnames or [])
    if not required_cols.issubset(found_cols):
        missing = sorted(required_cols - found_cols)
        raise HTTPException(status_code=400, detail=f"CSV missing required columns: {', '.join(missing)}")

    inserted = 0
    updated = 0
    skipped = 0
    errors: List[KeeperImportRowResult] = []

    for idx, row in enumerate(reader, start=2):
        season_raw = (row.get("season") or "").strip()
        entry_type = (row.get("entry_type") or "").strip().upper()
        owner_username = (row.get("owner_username") or "").strip()
        owner_team_name = (row.get("owner_team_name") or "").strip()
        from_owner_username = (row.get("from_owner_username") or "").strip()
        to_owner_username = (row.get("to_owner_username") or "").strip()
        note = (row.get("note") or "").strip()
        currency_type = ((row.get("currency_type") or "DRAFT_DOLLARS").strip() or "DRAFT_DOLLARS").upper()
        reference_id = (row.get("reference_id") or "").strip()

        if not season_raw.isdigit():
            skipped += 1
            errors.append(KeeperImportRowResult(row_number=idx, status="skipped", detail="invalid season"))
            continue
        season = _validate_season_year(int(season_raw))

        if entry_type not in VALID_ECON_ENTRY_TYPES:
            skipped += 1
            errors.append(
                KeeperImportRowResult(
                    row_number=idx,
                    status="skipped",
                    detail="entry_type must be STARTING_BUDGET, TRADE, or AWARD",
                )
            )
            continue

        try:
            amount = int(float((row.get("amount") or "").strip()))
            if amount <= 0:
                raise ValueError("amount must be positive")
        except ValueError:
            skipped += 1
            errors.append(KeeperImportRowResult(row_number=idx, status="skipped", detail="invalid amount"))
            continue

        from_owner_id: Optional[int] = None
        to_owner_id: Optional[int] = None

        if entry_type == "STARTING_BUDGET":
            owner = _resolve_owner_for_import(
                db,
                league_id=current_user.league_id,
                owner_username=owner_username,
                owner_team_name=owner_team_name,
            )
            if not owner:
                skipped += 1
                errors.append(
                    KeeperImportRowResult(row_number=idx, status="skipped", detail="owner not found")
                )
                continue
            to_owner_id = owner.id
        elif entry_type == "TRADE":
            from_owner = _resolve_owner_for_import(
                db,
                league_id=current_user.league_id,
                owner_username=from_owner_username,
                owner_team_name=None,
            )
            to_owner = _resolve_owner_for_import(
                db,
                league_id=current_user.league_id,
                owner_username=to_owner_username,
                owner_team_name=None,
            )
            if not from_owner or not to_owner:
                skipped += 1
                errors.append(
                    KeeperImportRowResult(
                        row_number=idx,
                        status="skipped",
                        detail="from_owner_username/to_owner_username not found",
                    )
                )
                continue
            if from_owner.id == to_owner.id:
                skipped += 1
                errors.append(
                    KeeperImportRowResult(row_number=idx, status="skipped", detail="trade owners must differ")
                )
                continue
            from_owner_id = from_owner.id
            to_owner_id = to_owner.id
        else:  # AWARD
            owner = _resolve_owner_for_import(
                db,
                league_id=current_user.league_id,
                owner_username=owner_username,
                owner_team_name=owner_team_name,
            )
            if not owner:
                skipped += 1
                errors.append(
                    KeeperImportRowResult(row_number=idx, status="skipped", detail="owner not found")
                )
                continue
            to_owner_id = owner.id

        if not reference_id:
            reference_id = (
                f"econ:{season}:{entry_type}:{from_owner_id or 0}:{to_owner_id or 0}:{amount}:{currency_type}"
            )

        existing_ledger = (
            db.query(models.EconomicLedger)
            .filter(
                models.EconomicLedger.league_id == current_user.league_id,
                models.EconomicLedger.reference_type == "ECON_HISTORY_IMPORT",
                models.EconomicLedger.reference_id == reference_id,
            )
            .first()
        )
        if existing_ledger:
            skipped += 1
            continue

        if dry_run:
            inserted += 1
            continue

        if entry_type == "STARTING_BUDGET" and to_owner_id is not None:
            budget = (
                db.query(models.DraftBudget)
                .filter(
                    models.DraftBudget.league_id == current_user.league_id,
                    models.DraftBudget.owner_id == to_owner_id,
                    models.DraftBudget.year == season,
                )
                .first()
            )
            if budget:
                budget.total_budget = amount
                updated += 1
            else:
                db.add(
                    models.DraftBudget(
                        league_id=current_user.league_id,
                        owner_id=to_owner_id,
                        year=season,
                        total_budget=amount,
                    )
                )

        record_ledger_entry(
            db=db,
            league_id=current_user.league_id,
            season_year=season,
            from_owner_id=from_owner_id,
            to_owner_id=to_owner_id,
            amount=amount,
            currency_type=currency_type,
            transaction_type=(
                "STARTING_BUDGET_IMPORT"
                if entry_type == "STARTING_BUDGET"
                else "TRADE_HISTORY_IMPORT"
                if entry_type == "TRADE"
                else "AWARD_HISTORY_IMPORT"
            ),
            reference_type="ECON_HISTORY_IMPORT",
            reference_id=reference_id,
            notes=note or f"Imported {entry_type.lower().replace('_', ' ')}",
        )
        inserted += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return EconomicImportResult(
        dry_run=dry_run,
        processed=inserted + updated + skipped,
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )


# --- Keeper settings endpoints (commissioner only) ---
class KeeperSettingsOut(BaseModel):
    max_keepers: int
    max_years_per_player: int
    deadline_date: Optional[datetime]
    waiver_policy: bool
    trade_deadline: Optional[datetime]
    drafted_only: bool
    cost_type: str
    cost_inflation: int

class KeeperSettingsUpdate(BaseModel):
    max_keepers: Optional[int] = None
    max_years_per_player: Optional[int] = None
    deadline_date: Optional[datetime] = None
    waiver_policy: Optional[bool] = None
    trade_deadline: Optional[datetime] = None
    drafted_only: Optional[bool] = None
    cost_type: Optional[str] = None
    cost_inflation: Optional[int] = None

@router.get("/settings", response_model=KeeperSettingsOut)
def get_keeper_settings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_admin),
):
    if not current_user.is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Commissioner required")
    rules = (
        db.query(models.KeeperRules)
        .filter(models.KeeperRules.league_id == current_user.league_id)
        .first()
    )
    if not rules:
        raise HTTPException(status_code=404, detail="Keeper rules not configured")
    return KeeperSettingsOut(
        max_keepers=rules.max_keepers,
        max_years_per_player=rules.max_years_per_player,
        deadline_date=rules.deadline_date,
        waiver_policy=rules.waiver_policy,
        trade_deadline=rules.trade_deadline,
        drafted_only=rules.drafted_only,
        cost_type=rules.cost_type,
        cost_inflation=rules.cost_inflation,
    )

@router.put("/settings")
def update_keeper_settings(
    update: KeeperSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_admin),
):
    if not current_user.is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Commissioner required")

    payload = update.model_dump(exclude_unset=True)

    boundary_report = validate_keeper_settings_boundary(payload)
    if not boundary_report.valid:
        raise HTTPException(status_code=400, detail=boundary_report.errors)

    dynamic_report = validate_keeper_settings_dynamic_rules(payload)
    if not dynamic_report.valid:
        raise HTTPException(status_code=400, detail=dynamic_report.errors)

    rules = (
        db.query(models.KeeperRules)
        .filter(models.KeeperRules.league_id == current_user.league_id)
        .first()
    )
    if not rules:
        # create if missing
        rules = models.KeeperRules(league_id=current_user.league_id)
        db.add(rules)
    # pydantic v2 uses model_dump instead of dict
    for field, val in payload.items():
        setattr(rules, field, val)
    db.commit()
    db.refresh(rules)
    return {"status": "updated"}
