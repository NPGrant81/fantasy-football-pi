import os
from datetime import timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from dotenv import load_dotenv

# Internal Imports
import models
import auth  # <--- WE USE THIS NOW instead of rewriting logic
from database import engine, get_db
# from routers import admin, team, matchups, players, league, advisor  <-- DELETE players
from routers import admin, team, matchups, league, advisor, dashboard

# app.include_router(players.router) <-- COMMENT THIS OUT
load_dotenv()

# --- APP SETUP ---
# Create Database Tables (Safe to run every time)
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- SECURITY: FIX CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows localhost:3000, localhost:5173, specific IPs, etc.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONNECT ROUTERS ---
app.include_router(admin.router)
app.include_router(team.router)
app.include_router(matchups.router)
# app.include_router(players.router) # Commented out to avoid conflict with manual /players below. 
# Once you move the player logic to routers/players.py, uncomment this and delete the manual route below.
app.include_router(league.router)
app.include_router(advisor.router)
app.include_router(dashboard.router)

# ---------------------------------------------------------
# AUTH ENDPOINTS (Using auth.py)
# ---------------------------------------------------------
@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1. Find the user
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    # 2. Verify password (using auth.py logic)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 3. Create Token (using auth.py logic)
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.id}

@app.get("/me")
def get_current_user_info(current_user: models.User = Depends(auth.get_current_user)):
    return {
        "user_id": current_user.id, 
        "username": current_user.username,
        "league_id": current_user.league_id, 
        "role": current_user.role,  # Added this so frontend knows if you are admin
        "is_commissioner": current_user.is_commissioner
    }

# ---------------------------------------------------------
# CORE ENDPOINTS (Salvaged from your old file)
# ---------------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "Fantasy Football API is Running!"}

@app.get("/owners")
def get_owners(db: Session = Depends(get_db)):
    # Filter out system accounts from the dropdown
    return db.query(models.User).filter(
        models.User.username.not_in(["Free Agent", "Obsolete", "free agent"])
    ).all()

@app.get("/players")
def get_players(db: Session = Depends(get_db)):
    return db.query(models.Player).all()

@app.get("/draft-history")
def get_draft_history(session_id: str, db: Session = Depends(get_db)):
    return db.query(models.DraftPick).filter(models.DraftPick.session_id == session_id).all()

# --- DRAFT ACTIONS ---
class DraftPickCreate(BaseModel):
    owner_id: int
    player_id: int 
    amount: int
    session_id: str

@app.post("/draft-pick")
def draft_player(pick: DraftPickCreate, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == pick.player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found in database")

    existing_pick = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == pick.player_id,
        models.DraftPick.session_id == pick.session_id
    ).first()
    
    if existing_pick:
        raise HTTPException(status_code=400, detail="Player already drafted!")

    new_pick = models.DraftPick(
        player_id=pick.player_id,
        owner_id=pick.owner_id,
        year=2026,
        amount=pick.amount,
        session_id=pick.session_id
    )
    db.add(new_pick)
    db.commit()
    db.refresh(new_pick)
    return new_pick