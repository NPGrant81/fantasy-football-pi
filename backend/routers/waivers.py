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
    # We removed owner_id from here because we will get it from the token securely

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
    # 1. Get the User's League
    league_id = current_user.league_id
    if not league_id:
        raise HTTPException(status_code=400, detail="You must be in a league to claim players.")

    # 2. Check if player is already owned IN THIS LEAGUE
    existing_ownership = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == claim.player_id,
        models.DraftPick.league_id == league_id 
    ).first()

    if existing_ownership:
        raise HTTPException(status_code=400, detail="Player is already owned in this league!")

    # 3. Add to team
    # We use session_id="WAIVER_WIRE" so we can filter these out of draft recaps later if needed
    new_add = models.DraftPick(
        owner_id=current_user.id,
        player_id=claim.player_id,
        amount=claim.bid_amount,
        session_id="WAIVER_WIRE",
        year=2026,
        league_id=league_id # <--- Critical!
    )
    
    db.add(new_add)
    db.commit()
    db.refresh(new_add)
    
    return {
        "status": "success", 
        "message": f"Player {claim.player_id} added to your roster!", 
        "player_id": claim.player_id
    }