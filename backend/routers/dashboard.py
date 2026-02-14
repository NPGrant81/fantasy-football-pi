# backend/routers/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import models

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/{owner_id}")
def get_manager_summary(owner_id: int, db: Session = Depends(get_db)):
    # 1. Get the owner's roster
    roster = db.query(models.Player).join(models.DraftPick).filter(
        models.DraftPick.owner_id == owner_id
    ).all()
    
    # 2. Get pending trade count (placeholder for now)
    trade_count = 0 
    
    # 3. Get league standing (placeholder)
    standing = "4th" 

    return {
        "roster": roster,
        "pending_trades": trade_count,
        "standing": standing,
        "roster_count": len(roster)
    }