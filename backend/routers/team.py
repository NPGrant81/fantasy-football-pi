from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from database import get_db
import models
import random

router = APIRouter(
    prefix="/team",
    tags=["Team Management"]
)

class RosterPlayer(BaseModel):
    player_id: int
    name: str
    position: str
    nfl_team: str
    acquisition_cost: int
    is_starter: bool
    status: str # NEW: Explicit status field (STARTER, BENCH, TAXI)
    bye_week: int
    ytd_score: float
    proj_score: float

class TeamResponse(BaseModel):
    owner_id: int
    team_name: str
    remaining_budget: int
    roster: List[RosterPlayer]

@router.get("/{owner_id}", response_model=TeamResponse)
def get_my_team(owner_id: int, db: Session = Depends(get_db)):
    owner = db.query(models.User).filter(models.User.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    
    # 1. GET ALL PLAYERS (Deduplicated)
    all_picks = db.query(models.DraftPick)\
        .filter(models.DraftPick.owner_id == owner_id)\
        .order_by(models.DraftPick.amount.desc())\
        .all()
    
    unique_players = {}
    for pick in all_picks:
        if pick.player_id not in unique_players:
             unique_players[pick.player_id] = pick

    # 2. PREPARE RAW LIST
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
                "status": "BENCH" # Default everyone to Bench first
            })

    # 3. SMART LINEUP ALGORITHM
    # Sort by cost (highest paid plays first)
    raw_roster.sort(key=lambda x: x["cost"], reverse=True)

    # Define limits
    limits = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DEF": 1, "K": 1}
    counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "DEF": 0, "K": 0}

    # Pass 1: Fill Mandatory Slots
    for p in raw_roster:
        pos = p["pos"]
        if pos in limits and counts[pos] < limits[pos]:
            p["status"] = "STARTER"
            counts[pos] += 1
    
    # Pass 2: Fill FLEX (1 spot: RB, WR, or TE)
    flex_filled = False
    for p in raw_roster:
        if p["status"] == "BENCH" and p["pos"] in ["RB", "WR", "TE"]:
            if not flex_filled:
                p["status"] = "STARTER"
                flex_filled = True
                break

    # 4. BUILD FINAL RESPONSE
    final_roster = []
    # Sort for UI: Starters first, then Bench. Inside that, sort by Position.
    pos_rank = {"QB": 1, "RB": 2, "WR": 3, "TE": 4, "DEF": 5, "K": 6}
    
    # Custom sort: Starters (0) vs Bench (1), then Position Rank
    raw_roster.sort(key=lambda x: (0 if x["status"] == "STARTER" else 1, pos_rank.get(x["pos"], 99)))

    for p in raw_roster:
        # Mock Data
        mock_bye = random.randint(5, 14)
        mock_ytd = round(random.uniform(50, 150), 2)
        mock_proj = round(random.uniform(10, 25), 2)

        final_roster.append(RosterPlayer(
            player_id=p["data"].id,
            name=p["data"].name,
            position=p["pos"],
            nfl_team=p["data"].nfl_team,
            acquisition_cost=p["cost"],
            is_starter=(p["status"] == "STARTER"),
            status=p["status"],
            bye_week=mock_bye,
            ytd_score=mock_ytd,
            proj_score=mock_proj
        ))

    return TeamResponse(
        owner_id=owner.id,
        team_name=f"Team {owner.username}",
        remaining_budget=100,
        roster=final_roster
    )