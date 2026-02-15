from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
import models
import auth # <--- Added this to get the user's league

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
    
    results = db.query(models.Player).filter(
        models.Player.name.ilike(search_term)
    ).limit(15).all()
    
    return results

@router.get("/waiver-wire")
def get_free_agents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user) # <--- Added dependency
):
    """
    Returns all players NOT currently owned in the user's specific league.
    """
    # 1. Get IDs of all players owned in THIS league only
    owned_ids_query = db.query(models.DraftPick.player_id).filter(
        models.DraftPick.league_id == current_user.league_id
    )
    
    # 2. Main Query: Find players NOT IN that list
    # "SELECT * FROM players WHERE id NOT IN (SELECT player_id FROM draft_picks WHERE league_id = X)"
    free_agents = db.query(models.Player).filter(
        ~models.Player.id.in_(owned_ids_query)
    ).limit(50).all()
    
    return free_agents