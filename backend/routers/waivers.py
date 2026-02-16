# backend/routers/waivers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import auth
from pydantic import BaseModel

router = APIRouter(
    prefix="/waivers",
    tags=["Waivers"]
)

# --- SCHEMAS ---
class WaiverClaimSchema(BaseModel):
    player_id: int
    bid_amount: int = 0

class DropPlayerSchema(BaseModel):
    player_id: int

# --- ENDPOINTS ---

@router.post("/claim")
def submit_waiver_claim(
    claim: WaiverClaimSchema, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Submits a claim for a free agent (First Come First Serve).
    """
    # 1.1 SECURITY CHECK: Ensure user is linked to a league
    league_id = current_user.league_id
    if not league_id:
        raise HTTPException(status_code=400, detail="You must be in a league to claim players.")

    # 1.2 OWNERSHIP CHECK: Ensure player isn't already taken in this specific league
    existing_ownership = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == claim.player_id,
        models.DraftPick.league_id == league_id 
    ).first()

    if existing_ownership:
        raise HTTPException(status_code=400, detail="Player is already owned in this league!")

    # 1.3 CAPACITY CHECK: Ensure the owner has room on their 14-man roster
    current_roster_count = db.query(models.DraftPick).filter(
        models.DraftPick.owner_id == current_user.id,
        models.DraftPick.league_id == league_id
    ).count()

    if current_roster_count >= 14: 
        raise HTTPException(
            status_code=400, 
            detail="Roster full! You must drop a player before adding another."
        )
    
    # 2.1 EXECUTION: Create the new DraftPick entry
    new_add = models.DraftPick(
        owner_id=current_user.id,
        player_id=claim.player_id,
        amount=claim.bid_amount,
        session_id="WAIVER_WIRE", # Tagged for filtering later
        year=2026,
        league_id=league_id
    )
    
    # 2.2 DATABASE COMMIT: Save the changes
    db.add(new_add)
    db.commit()
    db.refresh(new_add)
    
    return {
        "status": "success", 
        "message": f"Player {claim.player_id} added to your roster!", 
        "player_id": claim.player_id
    }

@router.post("/drop")
def drop_player(
    request: DropPlayerSchema,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # 1.1 LOCATE: Find the specific player pick owned by this user
    pick = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == request.player_id,
        models.DraftPick.owner_id == current_user.id,
        models.DraftPick.league_id == current_user.league_id
    ).first()

    # 1.2 VALIDATE: Ensure the pick actually exists before trying to delete
    if not pick:
        raise HTTPException(status_code=404, detail="Player not found on your roster.")

    # 2.1 EXECUTION: Remove the record from the database
    db.delete(pick)
    db.commit()
    
    return {"status": "success", "message": "Player dropped successfully"}