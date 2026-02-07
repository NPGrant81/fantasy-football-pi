from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models
from schemas import admin as schemas

# This creates a "mini-app" for Admin URLs
router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

# 1. Create a New League
@router.post("/leagues", response_model=schemas.LeagueResponse)
def create_league(league: schemas.LeagueCreate, db: Session = Depends(get_db)):
    # Check if name is taken
    existing = db.query(models.League).filter(models.League.name == league.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="League name already exists")
    
    # Create and Save
    new_league = models.League(name=league.name)
    db.add(new_league)
    db.commit()
    db.refresh(new_league)
    
    return new_league

# 2. Get All Leagues
@router.get("/leagues", response_model=List[schemas.LeagueResponse])
def get_leagues(db: Session = Depends(get_db)):
    return db.query(models.League).all()