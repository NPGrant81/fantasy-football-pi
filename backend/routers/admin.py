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
    # Note: If your User model doesn't have 'is_superuser', you can check username
    # or just remove this dependency for now while developing.
    # if not current_user.is_superuser:
    #     raise HTTPException(status_code=403, detail="Not authorized (Superuser only)")
    return current_user

# --- ENDPOINTS ---

@router.get("/leagues", response_model=List[LeagueAdminView])
def list_all_leagues(db: Session = Depends(get_db)):
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
def create_league(league_data: LeagueCreate, db: Session = Depends(get_db)):
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
def delete_league(league_id: int, db: Session = Depends(get_db)):
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
def list_all_users(db: Session = Depends(get_db)):
    """See every user on the site."""
    users = db.query(models.User).all()
    return [{"id": u.id, "username": u.username, "league_id": u.league_id} for u in users]

# --- NEW: TEST LEAGUE GENERATOR (Sandbox) ---
@router.post("/create-test-league")
def create_test_league(db: Session = Depends(get_db)):
    """
    Creates 'Test League 2026' and populates it with 12 dummy owners.
    """
    # 1. Create the League
    league_name = "Test League 2026"
    existing = db.query(models.League).filter(models.League.name == league_name).first()
    if existing:
         return {"message": "Test League already exists!", "league_id": existing.id}

    league = models.League(name=league_name)
    db.add(league)
    db.commit()
    db.refresh(league)

    # 2. Add Settings
    settings = models.LeagueSettings(league_id=league.id)
    db.add(settings)

    # 3. Create Dummy Owners
    dummy_names = ["Taco", "Ruxin", "Andre", "Kevin", "Pete", "Jenny", "Sofia", "Rafi", "DirtyRandy", "Ruspin", "Shivakamini", "ChalupaBatman"]
    
    for name in dummy_names:
        # Check if user exists, if not create
        user = db.query(models.User).filter(models.User.username == name).first()
        if not user:
            # Create new dummy user
            user = models.User(
                username=name, 
                hashed_password=auth.get_password_hash("password"), # Default password
                league_id=league.id,
                is_commissioner=False
            )
            db.add(user)
        else:
            # If they exist (maybe from a previous test), move them to this league
            user.league_id = league.id
            
    db.commit()
    
    return {"message": f"Test League '{league.name}' created with 12 owners!", "league_id": league.id}

# --- NFL DATA SYNC ---
@router.post("/tools/sync-nfl")
def sync_nfl_data(db: Session = Depends(get_db)):
    """
    Populates the database with a starter list of NFL players.
    """
    if db.query(models.Player).count() > 0:
        return {"message": "Players already synced! Database is populated."}

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
    ]

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