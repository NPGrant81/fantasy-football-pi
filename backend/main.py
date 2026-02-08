import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from pydantic import BaseModel
from jose import jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

# Internal Imports
import models
from database import SessionLocal, engine, get_db  
# FIX: Added 'players' to this import line
from routers import admin, team, matchups, players, league

load_dotenv()

# --- SECURITY CONFIG ---
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_if_env_missing")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120 

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- APP SETUP ---
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect Routers
app.include_router(admin.router)
app.include_router(team.router)
app.include_router(matchups.router)
app.include_router(players.router) 
app.include_router(league.router) # <--- Now this works because it's imported!

# --- AUTH HELPERS ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ---------------------------------------------------------
# CORE ENDPOINTS
# ---------------------------------------------------------
@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.id}

@app.get("/")
def read_root():
    return {"message": "Fantasy Football API is Running!"}

@app.get("/me")
def get_current_user_info(current_user: models.User = Depends(get_current_user)):
    return {
        "user_id": current_user.id, 
        "username": current_user.username,
        # NEW: Critical data points for the frontend
        "league_id": current_user.league_id, 
        "is_commissioner": current_user.is_commissioner
    }

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