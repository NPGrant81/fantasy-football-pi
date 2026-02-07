from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from database import get_db
import models

router = APIRouter(
    prefix="/matchups",
    tags=["Matchups"]
)

# --- Schemas ---
class MatchupSchema(BaseModel):
    id: int
    week: int
    home_team: str
    home_team_id: int
    home_score: float
    home_projected: float # NEW
    away_team: str
    away_team_id: int
    away_score: float
    away_projected: float # NEW
    is_completed: bool
    label: str # "Regular Season" or "Playoffs"
    date_range: str # "Sep 7 - Sep 11"

# --- Helper: Date Calculator ---
def get_week_info(week_num: int):
    # Mock Start Date: Sept 5, 2025
    season_start = datetime(2025, 9, 4) 
    week_start = season_start + timedelta(weeks=week_num-1)
    week_end = week_start + timedelta(days=4) # Thursday -> Monday
    
    date_str = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}"
    label = "Regular Season" if week_num <= 14 else "Playoffs"
    
    return label, date_str

# --- Endpoints ---
@router.get("/week/{week_num}", response_model=List[MatchupSchema])
def get_weekly_matchups(week_num: int, db: Session = Depends(get_db)):
    games = db.query(models.Matchup).filter(models.Matchup.week == week_num).all()
    label, date_str = get_week_info(week_num)

    results = []
    for game in games:
        home = db.query(models.User).filter(models.User.id == game.home_team_id).first()
        away = db.query(models.User).filter(models.User.id == game.away_team_id).first()
        
        if home and away:
            results.append(MatchupSchema(
                id=game.id,
                week=game.week,
                home_team=home.username,
                home_team_id=home.id,
                home_score=game.home_score,
                home_projected=game.home_projected,
                away_team=away.username,
                away_team_id=away.id,
                away_score=game.away_score,
                away_projected=game.away_projected,
                is_completed=game.is_completed,
                label=label,
                date_range=date_str
            ))
            
    return results

# NEW: Single Matchup Detail (For Game Center)
@router.get("/{matchup_id}", response_model=MatchupSchema)
def get_matchup_detail(matchup_id: int, db: Session = Depends(get_db)):
    game = db.query(models.Matchup).filter(models.Matchup.id == matchup_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Matchup not found")
        
    home = db.query(models.User).filter(models.User.id == game.home_team_id).first()
    away = db.query(models.User).filter(models.User.id == game.away_team_id).first()
    label, date_str = get_week_info(game.week)

    return MatchupSchema(
        id=game.id,
        week=game.week,
        home_team=home.username,
        home_team_id=home.id,
        home_score=game.home_score,
        home_projected=game.home_projected,
        away_team=away.username,
        away_team_id=away.id,
        away_score=game.away_score,
        away_projected=game.away_projected,
        is_completed=game.is_completed,
        label=label,
        date_range=date_str
    )