# backend/services/waiver_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException
import models

def process_claim(db: Session, user: models.User, player_id: int, bid: int, drop_id: int = None):
    # 1.1 VALIDATION: Check for League ID
    if not user.league_id:
        raise HTTPException(status_code=400, detail="User not in a league.")

    # 1.2 VALIDATION: Is target player already taken?
    existing = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == player_id,
        models.DraftPick.league_id == user.league_id 
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Player already owned!")

    # 2.1 CONDITIONAL DROP: If drop_id is provided, remove them first
    if drop_id:
        pick_to_drop = db.query(models.DraftPick).filter(
            models.DraftPick.player_id == drop_id,
            models.DraftPick.owner_id == user.id,
            models.DraftPick.league_id == user.league_id
        ).first()
        
        if not pick_to_drop:
            raise HTTPException(status_code=404, detail="Player to drop not found on your roster.")
        
        db.delete(pick_to_drop)
        # We don't commit yet; keep it in the same transaction
    
    # 2.2 ROSTER LIMIT CHECK: Only check if NOT dropping someone
    else:
        roster_count = db.query(models.DraftPick).filter(
            models.DraftPick.owner_id == user.id,
            models.DraftPick.league_id == user.league_id
        ).count()
        if roster_count >= 14:
            raise HTTPException(status_code=400, detail="Roster full! Select a player to drop.")

    # 3.1 EXECUTION: Create pick record
    new_pick = models.DraftPick(
        owner_id=user.id,
        player_id=player_id,
        amount=bid,
        session_id="WAIVER_WIRE",
        year=2026,
        league_id=user.league_id
    )
    
    db.add(new_pick)
    db.commit()
    db.refresh(new_pick)
    return new_pick

def process_drop(db: Session, user: models.User, player_id: int):
    # (Keep your existing process_drop logic here)
    pick = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == player_id,
        models.DraftPick.owner_id == user.id,
        models.DraftPick.league_id == user.league_id
    ).first()

    if not pick:
        raise HTTPException(status_code=404, detail="Player not on roster.")

    db.delete(pick)
    db.commit()
    return True