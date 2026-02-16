# backend/services/waiver_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException
import models

# 1.1.1 SERVICE: Handle the logic for claiming a player
def process_claim(db: Session, user: models.User, player_id: int, bid: int):
    # 1.1.1.1 VALIDATION: Check for League ID
    if not user.league_id:
        raise HTTPException(status_code=400, detail="User not in a league.")

    # 1.1.1.2 VALIDATION: Is player already taken?
    existing = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == player_id,
        models.DraftPick.league_id == user.league_id 
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Player already owned!")

    # 1.1.1.3 VALIDATION: Is roster full (14-man limit)?
    roster_count = db.query(models.DraftPick).filter(
        models.DraftPick.owner_id == user.id,
        models.DraftPick.league_id == user.league_id
    ).count()
    if roster_count >= 14:
        raise HTTPException(status_code=400, detail="Roster full!")

    # 2.1.1.1 EXECUTION: Create pick record
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

# 1.1.2 SERVICE: Handle dropping a player
def process_drop(db: Session, user: models.User, player_id: int):
    # 1.1.2.1 VALIDATION: Does the user actually own this player?
    pick = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == player_id,
        models.DraftPick.owner_id == user.id,
        models.DraftPick.league_id == user.league_id
    ).first()

    if not pick:
        raise HTTPException(status_code=404, detail="Player not on roster.")

    # 2.1.2.1 EXECUTION: Delete record
    db.delete(pick)
    db.commit()
    return True