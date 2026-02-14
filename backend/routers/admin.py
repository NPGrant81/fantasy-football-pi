# backend/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from database import get_db
import models
import auth

router = APIRouter(prefix="/admin", tags=["Site Admin"])

# --- SCHEMAS ---
class LeagueCreate(BaseModel):
    name: str

class LeagueAdminView(BaseModel):
    id: int
    name: str
    member_count: int

# --- DEPENDENCY: SUPERUSER ONLY ---
def get_superuser(current_user: models.User = Depends(auth.get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized (Superuser only)")
    return current_user

# --- ENDPOINTS ---

@router.get("/leagues", response_model=List[LeagueAdminView])
def list_all_leagues(db: Session = Depends(get_db), _: models.User = Depends(get_superuser)):
    """List every league on the platform."""
    leagues = db.query(models.League).all()
    return [
        LeagueAdminView(
            id=l.id, 
            name=l.name, 
            member_count=len(l.users) if l.users else 0
        ) for l in leagues
    ]

@router.post("/leagues")
def create_league(league_data: LeagueCreate, db: Session = Depends(get_db), _: models.User = Depends(get_superuser)):
    """Spin up a new league (e.g. 'TEST_LEAGUE')."""
    if db.query(models.League).filter(models.League.name == league_data.name).first():
        raise HTTPException(status_code=400, detail="League name taken")
    
    new_league = models.League(name=league_data.name)
    db.add(new_league)
    db.commit()
    db.refresh(new_league)
    
    # Init default settings immediately
    settings = models.LeagueSettings(league_id=new_league.id)
    db.add(settings)
    
    # Init default rules
    default_rules = [
        models.ScoringRule(league_id=new_league.id, category="Passing", description="Passing TD", points=4.0),
        models.ScoringRule(league_id=new_league.id, category="Rushing", description="Rushing TD", points=6.0),
        models.ScoringRule(league_id=new_league.id, category="Receiving", description="Reception (PPR)", points=1.0),
    ]
    db.add_all(default_rules)
    db.commit()
    
    return {"message": f"League '{new_league.name}' created!"}

@router.delete("/leagues/{league_id}")
def delete_league(league_id: int, db: Session = Depends(get_db), _: models.User = Depends(get_superuser)):
    """Nuclear option: Delete a league and all its data."""
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    
    # Delete dependent data first
    db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league_id).delete()
    db.query(models.ScoringRule).filter(models.ScoringRule.league_id == league_id).delete()
    
    # Kick users to Free Agency
    db.query(models.User).filter(models.User.league_id == league_id).update({"league_id": None})
    
    db.delete(league)
    db.commit()
    return {"message": "League deleted."}

@router.get("/users")
def list_all_users(db: Session = Depends(get_db), _: models.User = Depends(get_superuser)):
    """See every user on the site."""
    users = db.query(models.User).all()
    return [{"id": u.id, "username": u.username, "league_id": u.league_id, "is_admin": u.is_superuser} for u in users]

# --- ADD THIS TO THE BOTTOM OF admin.py ---

@router.post("/tools/sync-nfl")
def sync_nfl_data(db: Session = Depends(get_db)):
    """
    Populates the database with a starter list of NFL players.
    (In a real app, this would fetch from an external API).
    """
    # 1. Check if players already exist to avoid duplicates
    if db.query(models.Player).count() > 0:
        return {"message": "Players already synced! Database is populated."}

    # 2. Define a starter list of players
    initial_players = [
        {"name": "Patrick Mahomes", "position": "QB", "nfl_team": "KC"},
        {"name": "Josh Allen", "position": "QB", "nfl_team": "BUF"},
        {"name": "Jalen Hurts", "position": "QB", "nfl_team": "PHI"},
        {"name": "Christian McCaffrey", "position": "RB", "nfl_team": "SF"},
        {"name": "Austin Ekeler", "position": "RB", "nfl_team": "WAS"},
        {"name": "Justin Jefferson", "position": "WR", "nfl_team": "MIN"},
        {"name": "Ja'Marr Chase", "position": "WR", "nfl_team": "CIN"},
        {"name": "Tyreek Hill", "position": "WR", "nfl_team": "MIA"},
        {"name": "Travis Kelce", "position": "TE", "nfl_team": "KC"},
        {"name": "Mark Andrews", "position": "TE", "nfl_team": "BAL"},
        {"name": "Nick Bosa", "position": "DEF", "nfl_team": "SF"},
        {"name": "Micah Parsons", "position": "DEF", "nfl_team": "DAL"},
        # Add more here if you want...
    ]

    # 3. Loop through and add them to the DB
    for p in initial_players:
        db_player = models.Player(
            name=p["name"],
            position=p["position"],
            nfl_team=p["nfl_team"],
            adp=0.0,
            projected_points=0.0
        )
        db.add(db_player)

    db.commit()
    return {"message": f"Successfully added {len(initial_players)} players to the database."}