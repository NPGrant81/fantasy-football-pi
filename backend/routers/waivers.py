# backend/routers/waivers.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import models  # Assuming models.py is in the backend root 
from pydantic import BaseModel
from core.security import get_current_user  # Point to the new home of your bouncers

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

class DropPlayerSchema(BaseModel):
    player_id: int

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
        bid=claim.bid_amount
    )
    
    return {
        "status": "success", 
        "message": f"Player {result.player_id} added to your roster!", 
        "player_id": result.player_id
    }

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