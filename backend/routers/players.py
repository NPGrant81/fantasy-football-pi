from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
import models
import auth 

router = APIRouter(
    prefix="/players",
    tags=["Players"]
)

@router.get("/search")
def search_players(
    q: str = Query(..., min_length=2), 
    pos: str = Query("ALL"), # Merged: Added position filter
    db: Session = Depends(get_db)
):
    """
    Search for ANY player in the system. 
    Supports Global Search and specific Position Filtering.
    """
    search_term = f"%{q.strip()}%"
    
    query = db.query(models.Player).filter(
        models.Player.name.ilike(search_term)
    )

    # Merged logic: Filter by position if not 'ALL'
    if pos != "ALL":
        query = query.filter(models.Player.position == pos)
    
    results = query.limit(15).all()
    return results

@router.get("/waiver-wire")
def get_free_agents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Returns all players NOT currently owned in the user's specific league.
    """
    # 1. Get IDs of all players owned in THIS league only
    owned_ids_query = db.query(models.DraftPick.player_id).filter(
        models.DraftPick.league_id == current_user.league_id
    )
    
    # 2. Find players NOT IN that list
    free_agents = db.query(models.Player).filter(
        ~models.Player.id.in_(owned_ids_query)
    ).limit(50).all()
    
    return free_agents