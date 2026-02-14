# backend/routers/waivers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from pydantic import BaseModel

router = APIRouter(
    prefix="/waivers",
    tags=["Waivers"]
)

# Schema for incoming claims
class WaiverClaimSchema(BaseModel):
    owner_id: int
    player_id: int
    bid_amount: int = 0

@router.post("/claim")
def submit_waiver_claim(claim: WaiverClaimSchema, db: Session = Depends(get_db)):
    """
    Submits a claim for a free agent.
    For now, this is a direct add (First Come First Serve).
    """
    # 1. Check if player is already owned
    existing_ownership = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == claim.player_id
    ).first()

    if existing_ownership:
        raise HTTPException(status_code=400, detail="Player is already owned!")

    # 2. Add to team (We use the DraftPick table as the roster for now)
    # We use a special session_id "WAIVERS" or "FA" to distinguish from the draft
    new_add = models.DraftPick(
        owner_id=claim.owner_id,
        player_id=claim.player_id,
        amount=claim.bid_amount,
        session_id="WAIVER_WIRE",
        year=2026
    )
    
    db.add(new_add)
    db.commit()
    db.refresh(new_add)
    
    return {"status": "success", "message": "Player claimed successfully", "player_id": claim.player_id}