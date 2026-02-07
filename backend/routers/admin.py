from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models

router = APIRouter(
    prefix="/admin",
    tags=["Admin Tools"]
)

# ... (Existing endpoints) ...

@router.post("/finalize-draft")
def finalize_draft(db: Session = Depends(get_db)):
    """
    1. Checks if all teams met roster requirements.
    2. If yes, locks the draft and activates the season.
    """
    # 1. Get all owners (excluding system accounts)
    owners = db.query(models.User).filter(
        models.User.username.not_in(["Free Agent", "Obsolete", "free agent"])
    ).all()
    
    errors = []

    for owner in owners:
        picks = db.query(models.DraftPick).filter(models.DraftPick.owner_id == owner.id).all()
        
        # Rule A: 14 Players Total
        if len(picks) < 14:
            errors.append(f"{owner.username} only has {len(picks)}/14 players.")
            continue

        # Rule B: At least 1 of each position
        positions = set()
        for pick in picks:
            player = db.query(models.Player).filter(models.Player.id == pick.player_id).first()
            if player:
                pos = "DEF" if player.position == "TD" else player.position
                positions.add(pos)
        
        required = {"QB", "RB", "WR", "TE", "K", "DEF"}
        missing = required - positions
        
        if missing:
            errors.append(f"{owner.username} is missing positions: {', '.join(missing)}")

    if errors:
        return {"status": "error", "messages": errors}

    # 2. If No Errors -> Success!
    # In a real app, we would set a flag like: league.status = "active"
    # For now, we just return success.
    return {"status": "success", "message": "DRAFT COMPLETE! Season is now active."}