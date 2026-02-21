from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Set
from pydantic import BaseModel
from database import get_db
import models
from core.security import get_current_user, check_is_commissioner
import random

router = APIRouter(
    prefix="/team",
    tags=["Team"]
)

# --- 1. SCHEMAS (Rich Data) ---
class RosterPlayer(BaseModel):
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
    
    class Config:
        from_attributes = True

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
        final_list.append(RosterPlayer(
            player_id=p["data"].id,
            name=p["data"].name,
            position=p["pos"],
            nfl_team=p["data"].nfl_team,
            bye_week=p["data"].bye_week,
            acquisition_cost=p["cost"],
            is_starter=(p["status"] == "STARTER"),
            status=p["status"],
            projected_points=p["points"],
            is_locked=(p["data"].id in (locked_player_ids or set()))
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


def get_current_year() -> int:
    return datetime.now(timezone.utc).year


def validate_lineup_requirements(starters: List[models.DraftPick], settings: models.LeagueSettings) -> List[str]:
    slots = settings.starting_slots or {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1, "FLEX": 1}
    required_qb = int(slots.get("QB", 0) or 0)
    required_rb = int(slots.get("RB", 0) or 0)
    required_wr = int(slots.get("WR", 0) or 0)
    required_te = int(slots.get("TE", 0) or 0)
    required_k = int(slots.get("K", 0) or 0)
    required_def = int(slots.get("DEF", 0) or 0)
    required_flex = int(slots.get("FLEX", 0) or 0)

    counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "K": 0, "DEF": 0}
    for pick in starters:
        position = pick.player.position if pick.player else None
        if position == "TD":
            position = "DEF"
        if position in counts:
            counts[position] += 1

    errors: List[str] = []
    total_required = required_qb + required_rb + required_wr + required_te + required_k + required_def + required_flex
    if len(starters) < total_required:
        errors.append("not enough players")
    if len(starters) > total_required:
        errors.append("too many players")

    position_requirements = {
        "QB": required_qb,
        "RB": required_rb,
        "WR": required_wr,
        "TE": required_te,
        "K": required_k,
        "DEF": required_def,
    }
    for pos, required in position_requirements.items():
        if counts[pos] < required:
            errors.append(f"not enough {pos}")
        if counts[pos] > required and pos not in ["RB", "WR", "TE"]:
            errors.append(f"too many {pos}")

    extra_flex = max(0, counts["RB"] - required_rb) + max(0, counts["WR"] - required_wr) + max(0, counts["TE"] - required_te)
    if extra_flex < required_flex:
        errors.append("not enough FLEX (needs extra RB/WR/TE starter)")
    if extra_flex > required_flex:
        errors.append("too many FLEX-eligible starters (RB/WR/TE)")

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


@router.post("/lineup")
def update_lineup(
    payload: LineupUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    picks = db.query(models.DraftPick).filter(
        models.DraftPick.owner_id == current_user.id,
        models.DraftPick.league_id == current_user.league_id,
    ).all()

    season = get_current_year()
    locked_ids = get_locked_player_ids(db, [pick.player_id for pick in picks], season, payload.week)
    starter_ids = set(payload.starter_player_ids)

    for pick in picks:
        if pick.player_id in locked_ids:
            continue
        pick.current_status = "STARTER" if pick.player_id in starter_ids else "BENCH"

    db.commit()

    return {
        "message": "Lineup updated",
        "locked_player_ids": list(locked_ids),
    }


@router.post("/submit-lineup")
def submit_lineup(
    payload: LineupSubmitRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
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

    starters = [pick for pick in picks if (pick.current_status or "BENCH") == "STARTER"]
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