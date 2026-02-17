from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
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
    acquisition_cost: int
    is_starter: bool
    status: str  # "STARTER" or "BENCH"
    projected_points: float
    
    class Config:
        from_attributes = True

class RosterView(BaseModel):
    team_name: str
    owner_id: int
    players: List[RosterPlayer]

# --- 2. HELPER: THE SMART ALGORITHM ---
def organize_roster(picks, db: Session):
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
            raw_roster.append({
                "data": player,
                "pick": pick,
                "pos": display_pos,
                "cost": pick.amount,
                "status": "BENCH", # Default to Bench
                "points": player.projected_points or 0.0
            })

    # C. Sort by Cost (Highest paid players start first)
    raw_roster.sort(key=lambda x: x["cost"], reverse=True)

    # D. Assign Starters (Standard Format: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 DEF, 1 K)
    limits = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DEF": 1, "K": 1}
    counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "DEF": 0, "K": 0}

    # Pass 1: Mandatory Slots
    for p in raw_roster:
        pos = p["pos"]
        if pos in limits and counts[pos] < limits[pos]:
            p["status"] = "STARTER"
            counts[pos] += 1
    
    # Pass 2: FLEX (Best remaining RB/WR/TE)
    flex_filled = False
    for p in raw_roster:
        if p["status"] == "BENCH" and p["pos"] in ["RB", "WR", "TE"]:
            if not flex_filled:
                p["status"] = "STARTER"
                flex_filled = True
                break

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
            acquisition_cost=p["cost"],
            is_starter=(p["status"] == "STARTER"),
            status=p["status"],
            projected_points=p["points"]
        ))
        
    return final_list

# --- 3. ENDPOINTS ---

@router.get("/my-roster", response_model=RosterView)
def get_my_roster(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """Get the logged-in user's team, nicely sorted."""
    
    # 1. Get Picks
    picks = db.query(models.DraftPick).filter(
        models.DraftPick.owner_id == current_user.id,
        models.DraftPick.league_id == current_user.league_id
    ).all()

    # 2. Run Smart Algo
    sorted_players = organize_roster(picks, db)

    # 3. Return
    team_name = current_user.team_name if current_user.team_name else f"Team {current_user.username}"
    
    return RosterView(
        team_name=team_name,
        owner_id=current_user.id,
        players=sorted_players
    )

@router.get("/{owner_id}", response_model=RosterView)
def get_any_team(
    owner_id: int, 
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

    sorted_players = organize_roster(picks, db)
    
    team_name = owner.team_name if owner.team_name else f"Team {owner.username}"

    return RosterView(
        team_name=team_name,
        owner_id=owner.id,
        players=sorted_players
    )

@router.post("/update-name")
def update_team_name(
    name_data: dict, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    current_user.team_name = name_data.get("name")
    db.commit()
    return {"message": "Team name updated!", "new_name": current_user.team_name}