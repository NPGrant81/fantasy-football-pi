import os
from datetime import timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text 
from sqlalchemy.orm import Session
from pydantic import BaseModel
from dotenv import load_dotenv

# 1. LOAD ENV VARS FIRST (Before importing database)
load_dotenv()

# Internal Imports
import models
import auth
from database import engine, get_db

# Import Routers
from routers import admin, team, matchups, league, advisor, dashboard, players, waivers

# --- APP SETUP ---

# ---------------------------------------------------------
# NUCLEAR RESET BLOCK (RUN ONCE, THEN COMMENT OUT)
# ---------------------------------------------------------
# with engine.connect() as connection:
#     connection.execute(text("DROP TABLE IF EXISTS budgets CASCADE"))
#     connection.execute(text("DROP TABLE IF EXISTS draft_picks CASCADE"))
#     connection.execute(text("DROP TABLE IF EXISTS users CASCADE"))
#     connection.execute(text("DROP TABLE IF EXISTS players CASCADE"))
#     connection.commit()
# ---------------------------------------------------------

# Create tables if they don't exist
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- SECURITY: CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONNECT ROUTERS ---
# These handle the specialized logic (Search, Dashboard, Waivers)
app.include_router(admin.router)
app.include_router(team.router)
app.include_router(matchups.router)
app.include_router(league.router)
app.include_router(advisor.router)
app.include_router(dashboard.router)
app.include_router(players.router) 
app.include_router(waivers.router) 

# Note: 'trades' is commented out until you create that file
# app.include_router(trades.router) 

# ---------------------------------------------------------
# AUTH ENDPOINTS
# ---------------------------------------------------------
@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1. Find the user
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    # 2. Verify password
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 3. Create Token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # FIX: Return 'owner_id' so the Dashboard knows who you are!
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "owner_id": user.id,       # <--- Mapped from user.id
        "league_id": user.league_id 
    }

@app.get("/me")
def get_current_user_info(current_user: models.User = Depends(auth.get_current_user)):
    return {
        "user_id": current_user.id, 
        "username": current_user.username,
        "league_id": current_user.league_id, 
        # "role": current_user.role,
        "is_commissioner": current_user.is_commissioner
    }

# ---------------------------------------------------------
# LEGACY / DRAFT ENDPOINTS
# (Kept here to ensure DraftBoard.jsx doesn't break)
# ---------------------------------------------------------

@app.get("/owners")
def get_owners(db: Session = Depends(get_db)):
    return db.query(models.User).filter(
        models.User.username.not_in(["Free Agent", "Obsolete", "free agent"])
    ).all()

# NOTE: This endpoint is for the initial load. 
# The SEARCH functionality is now handled by players.router
@app.get("/players")
def get_all_players(db: Session = Depends(get_db)):
    return db.query(models.Player).limit(2000).all() # Added limit for safety

@app.get("/draft-history")
def get_draft_history(session_id: str, db: Session = Depends(get_db)):
    return db.query(models.DraftPick).filter(models.DraftPick.session_id == session_id).all()

class DraftPickCreate(BaseModel):
    owner_id: int
    player_id: int 
    amount: int
    session_id: str

@app.post("/draft-pick")
def draft_player(pick: DraftPickCreate, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == pick.player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

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