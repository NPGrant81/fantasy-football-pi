from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from ..database import get_db
from .. import models
from ..core.security import get_current_user, get_current_active_admin
from ..services import keeper_service

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

class KeeperPageResponse(BaseModel):
    selections: List[KeeperSelectionSchema]
    recommended: List[RecommendedSchema]
    selected_count: int
    max_allowed: int
    estimated_budget: int
    effective_budget: int
    ineligible: List[int] = []

class SubmitKeepersRequest(BaseModel):
    players: List[KeeperSelectionSchema]

# --- Owner routes ---
@router.get("/", response_model=KeeperPageResponse)
def get_my_keepers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Return keeper page data for the logged-in owner."""
    if not current_user.league_id:
        raise HTTPException(status_code=400, detail="User not in a league")
    # determine season from league configuration
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == current_user.league_id).first()
    season = settings.draft_year if settings else None
    if season is None:
        raise HTTPException(status_code=400, detail="League season not configured")

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
    ineligible_ids: list[int] = []
    if rules and rules.max_years_per_player is not None:
        # any player whose years_kept_count >= max should be flagged
        limit = rules.max_years_per_player
        ineligible_ids = [k.player_id for k in keepers if k.years_kept_count >= limit]

    return KeeperPageResponse(
        selections=selections,
        recommended=recommended,
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
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == current_user.league_id).first()
    season = settings.draft_year if settings else None
    if season is None:
        raise HTTPException(status_code=400, detail="League season not configured")

    # simple: delete existing pending entries for owner and add new ones
    db.query(models.Keeper).filter(
        models.Keeper.owner_id == current_user.id,
        models.Keeper.season == season,
        models.Keeper.status == "pending",
    ).delete(synchronize_session="fetch")
    for p in request.players:
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
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == current_user.league_id).first()
    season = settings.draft_year if settings else None
    if season is None:
        raise HTTPException(status_code=400, detail="League season not configured")

    # check lock date
    rules = db.query(models.KeeperRules).filter(models.KeeperRules.league_id == current_user.league_id).first()
    if rules and rules.deadline_date and rules.deadline_date < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Keeper window has closed")

    # update pending for this owner only
    count = (
        db.query(models.Keeper)
        .filter(
            models.Keeper.owner_id == current_user.id,
            models.Keeper.season == season,
            models.Keeper.status == "pending",
        )
        .update({"status": "locked", "locked_at": datetime.utcnow()}, synchronize_session="fetch")
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
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == current_user.league_id).first()
    season = settings.draft_year if settings else None
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
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == current_user.league_id).first()
    season = settings.draft_year if settings else None
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
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == current_user.league_id).first()
    season = settings.draft_year if settings else None
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
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == current_user.league_id).first()
    season = settings.draft_year if settings else None
    count = keeper_service.reset_keepers(db, current_user.league_id, season, owner_id)
    return {"cleared": count}


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
    for field, val in update.model_dump(exclude_unset=True).items():
        setattr(rules, field, val)
    db.commit()
    db.refresh(rules)
    return {"status": "updated"}
