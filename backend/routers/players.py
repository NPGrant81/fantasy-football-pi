# backend/routers/players.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
import models
from core.security import get_current_user, check_is_commissioner 
from services import player_service # 2.1.1 IMPORT the service logic

router = APIRouter(
    prefix="/players",
    tags=["Players"]
)

@router.get("/search")
def search_players(
    q: str = Query(..., min_length=2), 
    pos: str = Query("ALL"), 
    db: Session = Depends(get_db)
):
    # 2.2.1 CALL the service for searching
    return player_service.search_all_players(db, q, pos)

@router.get("/waiver-wire")
def get_free_agents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 2.3.1 CALL the service for free agent logic
    return player_service.get_league_free_agents(db, current_user.league_id)