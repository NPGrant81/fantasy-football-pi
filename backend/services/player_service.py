# backend/services/player_service.py
from sqlalchemy.orm import Session
from sqlalchemy import not_
import models

# 1.1.1 SERVICE: Search ALL players with position filtering
def search_all_players(db: Session, query_str: str, pos: str = "ALL"):
    search_term = f"%{query_str.strip()}%"
    query = db.query(models.Player).filter(models.Player.name.ilike(search_term))
    
    if pos != "ALL":
        query = query.filter(models.Player.position == pos)
    
    return query.limit(15).all()

# 1.1.2 SERVICE: Find Available Free Agents in a specific league
def get_league_free_agents(db: Session, league_id: int):
    # Subquery for IDs of all players owned in THIS league
    owned_ids_query = db.query(models.DraftPick.player_id).filter(
        models.DraftPick.league_id == league_id
    )
    
    # Return players NOT in that subquery
    return db.query(models.Player).filter(
        ~models.Player.id.in_(owned_ids_query)
    ).limit(50).all()