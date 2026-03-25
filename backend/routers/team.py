from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import Any, List, Optional, Dict, Set
from pydantic import BaseModel, ConfigDict
from ..database import get_db
from .. import models
from ..core.security import get_current_user, check_is_commissioner
from ..services.player_service import normalize_display_name as _normalize_player_name
import random
import os
import shutil
from pathlib import Path

router = APIRouter(
    prefix="/team",
    tags=["Team"]
)

# --- 1. SCHEMAS (Rich Data) ---
class RosterPlayer(BaseModel):
    # id property mirrors player_id so frontend code using either works
    id: int
    player_id: int
    name: str
    position: str
    nfl_team: str
    bye_week: Optional[int] = None
    acquisition_cost: int
    is_starter: bool
    status: str  # "STARTER" or "BENCH"
    projected_points: float
    is_locked: bool = False
    is_taxi: bool = False   # show taxi flag on roster
    
    # Pydantic v2 style
    model_config = ConfigDict(from_attributes=True)

class RosterView(BaseModel):
    team_name: str
    owner_id: int
    players: List[RosterPlayer]
    lineup_submitted: bool = False


class LineupUpdateRequest(BaseModel):
    week: int
    starter_player_ids: List[int]


class LineupSubmitRequest(BaseModel):
    week: int


class TaxiUpdateRequest(BaseModel):
    player_id: int

class TeamColorUpdateRequest(BaseModel):
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None

# --- 2. HELPER: THE SMART ALGORITHM ---
def organize_roster(picks, db: Session, locked_player_ids: Optional[Set[int]] = None):
    """
    Takes raw draft picks and organizes them into a valid Starting Lineup.
    """
    # A. Deduplicate (latest pick wins if dupes exist)
    unique_players = {}
    for pick in picks:
        unique_players[pick.player_id] = pick

    # B. Fetch Player Data & Build Raw List
    raw_roster = []
    for pid, pick in unique_players.items():
        player = db.query(models.Player).filter(models.Player.id == pid).first()
        if player:
            display_pos = "DEF" if player.position == "TD" else player.position
            status = pick.current_status if pick.current_status in ["STARTER", "BENCH"] else "BENCH"
            raw_roster.append({
                "data": player,
                "pick": pick,
                "pos": display_pos,
                "cost": pick.amount,
                "status": status,
                "points": player.projected_points or 0.0
            })

    # C. Sort by Cost (Highest paid players first)
    raw_roster.sort(key=lambda x: x["cost"], reverse=True)

    # D. Fallback auto-assignment for legacy rows that have no starter markers yet
    has_explicit_starters = any(p["status"] == "STARTER" for p in raw_roster)
    if not has_explicit_starters:
        limits = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DEF": 1, "K": 1}
        counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "DEF": 0, "K": 0}

        for p in raw_roster:
            pos = p["pos"]
            if pos in limits and counts[pos] < limits[pos]:
                p["status"] = "STARTER"
                counts[pos] += 1

        flex_filled = False
        for p in raw_roster:
            if p["status"] == "BENCH" and p["pos"] in ["RB", "WR", "TE"] and not flex_filled:
                p["status"] = "STARTER"
                flex_filled = True

    # E. Final Sort (Starters at top, organized by position)
    pos_rank = {"QB": 1, "RB": 2, "WR": 3, "TE": 4, "DEF": 5, "K": 6}
    raw_roster.sort(key=lambda x: (0 if x["status"] == "STARTER" else 1, pos_rank.get(x["pos"], 99)))

    # F. Convert to Schema
    final_list = []
    for p in raw_roster:
        # taxi picks should still appear in the roster listing (bench section)
        # with an explicit flag so the client can segregate them visually.
        final_list.append(RosterPlayer(
            id=p["data"].id,
            player_id=p["data"].id,
            name=_normalize_player_name(p["data"].name),
            position=p["pos"],
            nfl_team=p["data"].nfl_team,
            bye_week=p["data"].bye_week,
            acquisition_cost=p["cost"],
            is_starter=(p["status"] == "STARTER"),
            status=p["status"],
            projected_points=p["points"],
            is_locked=(p["data"].id in (locked_player_ids or set())),
            is_taxi=bool(p["pick"].is_taxi)
        ))
        
    return final_list


def get_locked_player_ids(db: Session, player_ids: List[int], season: int, week: int) -> Set[int]:
    if not player_ids:
        return set()
    rows = db.query(models.PlayerWeeklyStat.player_id).filter(
        models.PlayerWeeklyStat.player_id.in_(player_ids),
        models.PlayerWeeklyStat.season == season,
        models.PlayerWeeklyStat.week == week,
    ).all()
    return {row[0] for row in rows}


def is_week_finalized(db: Session, league_id: int, week: int) -> bool:
    matchups = (
        db.query(models.Matchup)
        .filter(
            models.Matchup.league_id == league_id,
            models.Matchup.week == week,
        )
        .all()
    )
    if not matchups:
        return False
    return all(bool(m.is_completed) and str(m.game_status or "").upper() == "FINAL" for m in matchups)


def assert_week_not_finalized(db: Session, league_id: int, week: int) -> None:
    if is_week_finalized(db, league_id, week):
        raise HTTPException(
            status_code=400,
            detail=f"Week {week} is finalized and lineup edits are locked.",
        )


def get_current_year() -> int:
    return datetime.now(timezone.utc).year


def _build_canonical_starter_slots(max_limits: Dict[str, int], required_total: int) -> Dict[str, int]:
    slots: Dict[str, int] = {
        "QB": 1 if max_limits["QB"] > 0 else 0,
        "RB": min(2, max_limits["RB"]) if max_limits["RB"] > 0 else 0,
        "WR": min(2, max_limits["WR"]) if max_limits["WR"] > 0 else 0,
        "TE": 1 if max_limits["TE"] > 0 else 0,
        "K": 1 if max_limits["K"] > 0 else 0,
        "DEF": 1 if max_limits["DEF"] > 0 else 0,
        "FLEX": 1 if max_limits["FLEX"] > 0 else 0,
    }

    total_minimums = sum(slots.values())
    if required_total > 0 and total_minimums > required_total:
        for pos in ("FLEX", "K", "TE", "WR", "RB", "QB", "DEF"):
            while slots[pos] > 0 and total_minimums > required_total:
                slots[pos] -= 1
                total_minimums -= 1
            if total_minimums <= required_total:
                break

    return slots


def validate_lineup_requirements(starters: List[models.DraftPick], settings: models.LeagueSettings) -> List[str]:
    """Validate that a proposed set of starters satisfies the league's slot rules.

    The algorithm mirrors the client-side logic used in the React roster page.  It
    attempts to assign players to each non-FLEX slot first, then fills any FLEX
    slots with the best remaining RB/WR/TE candidates.  Errors are generated when
    there aren't enough players to fill the required number of slots, when there
    are too many players, or when a specific slot (including FLEX) has too many
    or too few assigned players.

    A separate `ALLOW_PARTIAL_LINEUP` flag allows teams to submit with fewer
    than the active roster size. When enabled, minimum-count errors (including
    slot-specific shortages such as FLEX) are non-blocking, while over-capacity
    checks ("too many ...") still apply.
    """

    # note: starting_slots JSON may contain configuration keys such as
    # ACTIVE_ROSTER_SIZE, MAX_QB, ALLOW_PARTIAL_LINEUP, etc.  only a subset of
    # entries actually represent position slots that should be counted.
    raw_slots = settings.starting_slots or {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "K": 1,
        "DEF": 1,
        "FLEX": 1,
    }

    allow_partial_lineup = int(raw_slots.get("ALLOW_PARTIAL_LINEUP", 0) or 0) == 1

    required_total = int(
        raw_slots.get(
            "ACTIVE_ROSTER_SIZE",
            int(settings.roster_size or 9),
        )
        or 0
    )

    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    max_limits: Dict[str, int] = {
        "QB": max(1, min(3, _to_int(raw_slots.get("MAX_QB", raw_slots.get("QB", 1)), 1))),
        "RB": max(1, min(5, _to_int(raw_slots.get("MAX_RB", raw_slots.get("RB", 3)), 3))),
        "WR": max(1, min(5, _to_int(raw_slots.get("MAX_WR", raw_slots.get("WR", 3)), 3))),
        "TE": max(1, min(3, _to_int(raw_slots.get("MAX_TE", raw_slots.get("TE", 2)), 2))),
        "K": max(0, min(1, _to_int(raw_slots.get("MAX_K", raw_slots.get("K", 1)), 1))),
        "DEF": max(0, min(1, _to_int(raw_slots.get("MAX_DEF", raw_slots.get("DEF", 1)), 1))),
        "FLEX": max(0, min(2, _to_int(raw_slots.get("MAX_FLEX", raw_slots.get("FLEX", 1)), 1))),
    }

    slots = _build_canonical_starter_slots(max_limits, required_total)

    # --- build a simple pool of starters by position ---
    pools = {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "K": 0, "DEF": 0}
    for pick in starters:
        # taxi picks are not eligible for starting lineup calculations
        if getattr(pick, "is_taxi", False):
            continue
        position = pick.player.position if pick.player else None
        if position == "TD":
            position = "DEF"
        if position in pools:
            pools[position] += 1

    # --- assign slots greedily, non-FLEX first ---
    actual_slot_counts: Dict[str, int] = {}
    for pos, slot_count in slots.items():
        if pos == "FLEX" or not slot_count:
            continue
        available = pools.get(pos, 0)
        assigned = min(slot_count, available)
        if assigned:
            actual_slot_counts[pos] = assigned

    # handle FLEX separately using leftover RB/WR/TE players
    flex_slots = slots.get("FLEX", 0)
    if flex_slots > 0:
        total_eligible = (
            pools.get("RB", 0) + pools.get("WR", 0) + pools.get("TE", 0)
        )
        used_non_flex = (
            actual_slot_counts.get("RB", 0)
            + actual_slot_counts.get("WR", 0)
            + actual_slot_counts.get("TE", 0)
        )
        remaining = max(0, total_eligible - used_non_flex)
        flex_assigned = min(flex_slots, remaining)
        if flex_assigned:
            actual_slot_counts["FLEX"] = flex_assigned

    errors: List[str] = []
    if len(starters) < required_total and not allow_partial_lineup:
        errors.append("not enough players")
    if len(starters) > required_total:
        errors.append("too many players")

    # validate each configured slot
    for pos, required_count in slots.items():
        required = int(required_count or 0)
        if required <= 0:
            continue
        actual = actual_slot_counts.get(pos, 0)
        if actual < required and not allow_partial_lineup:
            if pos == "FLEX":
                errors.append(
                    "not enough FLEX (needs extra RB/WR/TE starter)"
                )
            else:
                errors.append(f"not enough {pos}")
        if actual > required:
            if pos == "FLEX":
                errors.append(
                    "too many FLEX-eligible starters (RB/WR/TE)"
                )
            else:
                errors.append(f"too many {pos}")

    return errors

# --- 3. ENDPOINTS ---

@router.get("/my-roster", response_model=RosterView)
def get_my_roster(
    week: int = Query(1, ge=1, le=18),
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """Get the logged-in user's team, nicely sorted."""
    
    # 1. Get Picks
    picks = db.query(models.DraftPick).filter(
        models.DraftPick.owner_id == current_user.id,
        models.DraftPick.league_id == current_user.league_id
    ).all()

    season = get_current_year()
    locked_ids = get_locked_player_ids(db, [pick.player_id for pick in picks], season, week)

    sorted_players = organize_roster(picks, db, locked_player_ids=locked_ids)

    submitted = db.query(models.LineupSubmission).filter(
        models.LineupSubmission.owner_id == current_user.id,
        models.LineupSubmission.league_id == current_user.league_id,
        models.LineupSubmission.season == season,
        models.LineupSubmission.week == week,
    ).first()

    # 3. Return
    team_name = current_user.team_name if current_user.team_name else f"Team {current_user.username}"
    
    return RosterView(
        team_name=team_name,
        owner_id=current_user.id,
        players=sorted_players,
        lineup_submitted=bool(submitted)
    )

@router.get("/{owner_id}", response_model=RosterView)
def get_any_team(
    owner_id: int, 
    week: int = Query(1, ge=1, le=18),
    db: Session = Depends(get_db)
):
    """View ANY user's team (for 'League' pages)."""
    try:
        owner = db.query(models.User).filter(models.User.id == owner_id).first()
        if not owner:
            raise HTTPException(status_code=404, detail="Owner not found")

        picks = db.query(models.DraftPick).filter(
            models.DraftPick.owner_id == owner.id,
            models.DraftPick.league_id == owner.league_id
        ).all()

        season = get_current_year()
        locked_ids = get_locked_player_ids(db, [pick.player_id for pick in picks], season, week)
        sorted_players = organize_roster(picks, db, locked_player_ids=locked_ids)

        submitted = db.query(models.LineupSubmission).filter(
            models.LineupSubmission.owner_id == owner.id,
            models.LineupSubmission.league_id == owner.league_id,
            models.LineupSubmission.season == season,
            models.LineupSubmission.week == week,
        ).first()

        team_name = owner.team_name if owner.team_name else f"Team {owner.username}"

        return RosterView(
            team_name=team_name,
            owner_id=owner.id,
            players=sorted_players,
            lineup_submitted=bool(submitted)
        )
    except Exception as exc:
        # log stack trace so server log contains the error
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        # re-raise to preserve standard FastAPI error handling
        raise


@router.post("/lineup")
def update_lineup(
    payload: LineupUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    assert_week_not_finalized(db, current_user.league_id, payload.week)

    picks = db.query(models.DraftPick).filter(
        models.DraftPick.owner_id == current_user.id,
        models.DraftPick.league_id == current_user.league_id,
    ).all()

    season = get_current_year()
    locked_ids = get_locked_player_ids(db, [pick.player_id for pick in picks], season, payload.week)
    starter_ids = set(payload.starter_player_ids)

    for pick in picks:
        if pick.is_taxi:
            # taxi players are never eligible to be starters
            continue
        if pick.player_id in locked_ids:
            continue
        pick.current_status = "STARTER" if pick.player_id in starter_ids else "BENCH"

    db.commit()

    return {
        "message": "Lineup updated",
        "locked_player_ids": list(locked_ids),
    }


# --- 4. TAXI ENDPOINTS ---
@router.post("/taxi/promote")
def promote_taxi(
    payload: TaxiUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Move a player from taxi to bench (owner only)."""
    pick = db.query(models.DraftPick).filter(
        models.DraftPick.owner_id == current_user.id,
        models.DraftPick.player_id == payload.player_id,
    ).first()
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    if not pick.is_taxi:
        return {"message": "Player not on taxi squad"}
    pick.is_taxi = False
    db.commit()
    return {"message": "Player promoted from taxi"}


@router.post("/taxi/demote")
def demote_taxi(
    payload: TaxiUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Move a player from bench to taxi (owner only)."""
    pick = db.query(models.DraftPick).filter(
        models.DraftPick.owner_id == current_user.id,
        models.DraftPick.player_id == payload.player_id,
    ).first()
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    if pick.is_taxi:
        return {"message": "Player already on taxi squad"}
    pick.is_taxi = True
    # also ensure it's not marked starter
    pick.current_status = "BENCH"
    db.commit()
    return {"message": "Player demoted to taxi"}


@router.post("/submit-lineup")
def submit_lineup(
    payload: LineupSubmitRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    assert_week_not_finalized(db, current_user.league_id, payload.week)

    picks = db.query(models.DraftPick).filter(
        models.DraftPick.owner_id == current_user.id,
        models.DraftPick.league_id == current_user.league_id,
    ).all()

    settings = db.query(models.LeagueSettings).filter(
        models.LeagueSettings.league_id == current_user.league_id
    ).first()
    if not settings:
        settings = models.LeagueSettings(league_id=current_user.league_id)
        db.add(settings)
        db.flush()

    # exclude any taxi players from the set of starters
    starters = [pick for pick in picks if (pick.current_status or "BENCH") == "STARTER" and not pick.is_taxi]
    errors = validate_lineup_requirements(starters, settings)
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    season = get_current_year()
    submission = db.query(models.LineupSubmission).filter(
        models.LineupSubmission.owner_id == current_user.id,
        models.LineupSubmission.league_id == current_user.league_id,
        models.LineupSubmission.season == season,
        models.LineupSubmission.week == payload.week,
    ).first()
    now = datetime.now(timezone.utc).isoformat()

    if submission:
        submission.submitted_at = now
    else:
        submission = models.LineupSubmission(
            owner_id=current_user.id,
            league_id=current_user.league_id,
            season=season,
            week=payload.week,
            submitted_at=now,
        )
        db.add(submission)

    db.commit()
    return {
        "message": "Roster submitted",
        "week": payload.week,
        "submitted_at": now,
    }

@router.post("/update-name")
def update_team_name(
    name_data: dict, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    current_user.team_name = name_data.get("name")
    db.commit()
    return {"message": "Team name updated!", "new_name": current_user.team_name}


@router.post("/update-colors")
def update_team_colors(
    color_data: TeamColorUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update team colors for matchup visualization."""
    if color_data.color_primary:
        current_user.team_color_primary = color_data.color_primary
    if color_data.color_secondary:
        current_user.team_color_secondary = color_data.color_secondary
    
    db.commit()
    return {
        "message": "Team colors updated!",
        "color_primary": current_user.team_color_primary,
        "color_secondary": current_user.team_color_secondary
    }


@router.post("/upload-logo")
async def upload_team_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Upload a team logo image."""
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only images allowed.")
    
    # Create upload directory if it doesn't exist
    upload_dir = Path("frontend/public/team-logos")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    filename = f"team_{current_user.id}_{int(datetime.now(timezone.utc).timestamp())}.{file_ext}"
    file_path = upload_dir / filename
    
    # Save file
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Update user record with relative URL
    logo_url = f"/team-logos/{filename}"
    current_user.team_logo_url = logo_url
    db.commit()
    
    return {
        "message": "Team logo uploaded successfully!",
        "logo_url": logo_url
    }


@router.delete("/delete-logo")
def delete_team_logo(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Remove team logo and revert to default."""
    if current_user.team_logo_url:
        # Optionally delete the file from disk
        try:
            logo_path = Path(f"frontend/public{current_user.team_logo_url}")
            if logo_path.exists():
                logo_path.unlink()
        except Exception:
            pass  # Don't fail if file deletion fails
        
        current_user.team_logo_url = None
        db.commit()
    
    return {"message": "Team logo removed successfully!"}