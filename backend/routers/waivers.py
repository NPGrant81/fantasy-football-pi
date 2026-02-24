# backend/routers/waivers.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import models  # Assuming models.py is in the backend root 
from pydantic import BaseModel
from typing import Optional
from core.security import get_current_user, get_current_active_admin  # Point to the new home of your bouncers

# 1.1.1 IMPORT the service logic we just built
from services import waiver_service 

router = APIRouter(
    prefix="/waivers",
    tags=["Waivers"]
)

# --- 1.2 SCHEMAS ---
class WaiverClaimSchema(BaseModel):
    player_id: int
    bid_amount: int = 0
    drop_player_id: Optional[int] = None

class DropPlayerSchema(BaseModel):
    player_id: int


# schema for outputting claims (used by commissioner audit)
class WaiverClaimOut(BaseModel):
    id: int
    user_id: int
    username: Optional[str] = None
    player_id: int
    player_name: Optional[str] = None
    drop_player_id: Optional[int] = None
    drop_player_name: Optional[str] = None
    bid_amount: int
    status: str

    class Config:
        orm_mode = True

# --- 2.1 ENDPOINTS ---

@router.post("/claim")
def submit_waiver_claim(
    claim: WaiverClaimSchema, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Submits a claim via the Waiver Service.
    """
    # 2.1.1 CALL the service to handle validations (1.x) and execution (2.x)
    result = waiver_service.process_claim(
        db=db, 
        user=current_user, 
        player_id=claim.player_id, 
        bid=claim.bid_amount,
        drop_id=claim.drop_player_id,
    )
    
    return {
        "status": "success", 
        "message": f"Player {result.player_id} added to your roster!", 
        "player_id": result.player_id
    }

@router.get("/claims", response_model=list[WaiverClaimOut])
def list_waiver_claims(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_admin),
):
    """
    Returns all waiver claims for the commissioner's league.  Used by
    administrator pages to audit waiver activity.
    """
    # safety: ensure only commissioners can call even if dependency bypassed
    if not current_user.is_commissioner:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: commissioner privileges required."
        )

    claims = (
        db.query(models.WaiverClaim)
        .filter(models.WaiverClaim.league_id == current_user.league_id)
        .all()
    )

    # build plain objects with related names for convenience
    result = []
    for c in claims:
        result.append({
            "id": c.id,
            "league_id": c.league_id,
            "user_id": c.user_id,
            "username": c.user.username if c.user else None,
            "player_id": c.player_id,
            "player_name": c.target_player.name if c.target_player else None,
            "drop_player_id": c.drop_player_id,
            "drop_player_name": c.drop_player.name if c.drop_player else None,
            "bid_amount": c.bid_amount,
            "status": c.status,
        })
    return result
@router.post("/drop")
def drop_player(
    request: DropPlayerSchema,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Drops a player via the Waiver Service.
    """
    # 2.2.1 CALL the service to handle the deletion logic
    waiver_service.process_drop(
        db=db, 
        user=current_user, 
        player_id=request.player_id
    )
    
    return {"status": "success", "message": "Player dropped successfully"}