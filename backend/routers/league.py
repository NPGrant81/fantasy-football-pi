from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from database import get_db
import models
import auth # Use our new auth system

# FIX 1: Changed prefix to "/leagues" (Plural) to match Frontend
router = APIRouter(
    prefix="/leagues",
    tags=["League"]
)

# --- Schemas (Keep them here for simplicity) ---
class LeagueCreate(BaseModel):
    name: str

class LeagueSummary(BaseModel):
    id: int
    name: str

class AddMemberRequest(BaseModel):
    username: str # Better to add by username than ID

# --- Endpoints ---

@router.get("/", response_model=List[LeagueSummary])
def get_leagues(db: Session = Depends(get_db)):
    """List all available leagues."""
    leagues = db.query(models.League).all()
    return [LeagueSummary(id=l.id, name=l.name) for l in leagues]

@router.post("/", response_model=LeagueSummary)
def create_league(league_data: LeagueCreate, db: Session = Depends(get_db)):
    """Create a new league + Default Scoring Rules."""
    # 1. Check if name exists
    existing = db.query(models.League).filter(models.League.name == league_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="League name already taken")
    
    # 2. Create League
    new_league = models.League(name=league_data.name)
    db.add(new_league)
    db.commit()
    db.refresh(new_league)
    
    # 3. Create Default Scoring Rules (The NEW way)
    # We add these so the AI Advisor has something to read immediately.
    default_rules = [
        models.ScoringRule(league_id=new_league.id, category="Passing", description="Passing TD", points=4.0),
        models.ScoringRule(league_id=new_league.id, category="Passing", description="Interception", points=-2.0),
        models.ScoringRule(league_id=new_league.id, category="Rushing", description="Rushing TD", points=6.0),
        models.ScoringRule(league_id=new_league.id, category="Receiving", description="Reception (PPR)", points=1.0),
    ]
    db.add_all(default_rules)
    db.commit()

    return LeagueSummary(id=new_league.id, name=new_league.name)

@router.post("/join")
def join_league(league_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Let a user join a specific league."""
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    
    current_user.league_id = league_id
    db.commit()
    return {"message": f"Welcome to {league.name}!"}