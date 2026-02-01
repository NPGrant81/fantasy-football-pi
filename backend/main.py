from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import List, Optional

from database import SessionLocal, engine
import models

# Create the App
app = FastAPI()

# Enable CORS (Allows your future React website to talk to this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------

@app.get("/")
def read_root():
    return {"message": "Fantasy Football API is Running!"}

@app.get("/owners")
def get_owners(db: Session = Depends(get_db)):
    """Get a list of all league owners"""
    return db.query(models.User).all()

@app.get("/players")
def get_players(position: Optional[str] = None, team: Optional[str] = None, db: Session = Depends(get_db)):
    """Get players, filtered by Position or NFL Team"""
    query = db.query(models.Player)
    if position:
        query = query.filter(models.Player.position == position)
    if team:
        query = query.filter(models.Player.nfl_team == team)
    return query.limit(100).all()

@app.get("/draft-history")
def get_draft_history(year: Optional[int] = None, db: Session = Depends(get_db)):
    """Get the full draft history"""
    query = db.query(models.DraftPick)
    if year:
        query = query.filter(models.DraftPick.year == year)
    return query.order_by(models.DraftPick.year.desc(), models.DraftPick.amount.desc()).all()

@app.get("/stats/top-spenders")
def get_top_spenders(db: Session = Depends(get_db)):
    """Who has spent the most money in league history?"""
    results = db.query(
        models.User.username, 
        func.sum(models.DraftPick.amount).label('total_spent')
    ).join(models.DraftPick).group_by(models.User.id).order_by(text("total_spent DESC")).all()
    
    return [{"owner": row.username, "total_spent": row.total_spent} for row in results]