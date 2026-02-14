from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
import models

router = APIRouter(
    prefix="/players",
    tags=["Players"]
)

@router.get("/search")
def search_players(q: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    """
    Search for ANY player in the system (Drafted or Free Agent).
    Powers the 'Global Search' and 'War Room' lookups.
    """
    search_term = f"%{q.strip()}%"
    
    # We use ilike for case-insensitive matching
    results = db.query(models.Player).filter(
        models.Player.name.ilike(search_term)
    ).limit(15).all()
    
    return results

@router.get("/waiver-wire")
def get_free_agents(db: Session = Depends(get_db)):
    """
    SALVAGED: Returns all players NOT in the draft_picks table.
    """
    # Subquery: Get all drafted player IDs
    drafted_ids = db.query(models.DraftPick.player_id).subquery()
    
    # Main Query: Find players NOT IN that list
    free_agents = db.query(models.Player).filter(
        models.Player.id.not_in(drafted_ids)
    ).limit(50).all()
    
    return free_agents