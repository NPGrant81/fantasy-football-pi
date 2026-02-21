# backend/routers/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy import or_
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
    
    owner = db.query(models.User).filter(models.User.id == owner_id).first()
    if owner and owner.league_id:
        trade_count = (
            db.query(models.TradeProposal)
            .filter(
                models.TradeProposal.league_id == owner.league_id,
                models.TradeProposal.status == "PENDING",
                or_(
                    models.TradeProposal.from_user_id == owner_id,
                    models.TradeProposal.to_user_id == owner_id,
                ),
            )
            .count()
        )
    else:
        trade_count = 0
    
    # 3. Get league standing (placeholder)
    standing = "4th" 

    return {
        "roster": roster,
        "pending_trades": trade_count,
        "standing": standing,
        "roster_count": len(roster)
    }