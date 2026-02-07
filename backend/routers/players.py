from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import models

router = APIRouter(
    prefix="/players",
    tags=["Players"]
)

@router.get("/waiver-wire")
def get_free_agents(db: Session = Depends(get_db)):
    """
    Returns all players who are NOT in the draft_picks table.
    """
    # Subquery: Get all drafted player IDs
    drafted_ids = db.query(models.DraftPick.player_id).subquery()
    
    # Main Query: Find players NOT IN that list
    free_agents = db.query(models.Player).filter(
        models.Player.id.not_in(drafted_ids)
    ).limit(50).all() # Limit to 50 for performance
    
    return free_agents