import os
from dotenv import load_dotenv

load_dotenv() # <--- This loads the .env file immediately
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import List, Optional

from database import SessionLocal, engine
import models

# Create the App
app = FastAPI()
# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# --- SECURITY CONFIG ---
# OLD: SECRET_KEY = "supersecretkey"
# NEW:
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_if_env_missing")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120 # Tokens last 2 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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
# -----------------------
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
@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1. Check if user exists
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    # 2. Check if password matches
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    # 3. Create the Token
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.id}

@app.get("/")
def read_root():
    return {"message": "Fantasy Football API is Running!"}

# --- NEW: Identify Current User ---
@app.get("/me")
def get_current_user_info(current_user: models.User = Depends(get_current_user)):
    return {"user_id": current_user.id, "username": current_user.username}

@app.get("/owners")
def get_owners(db: Session = Depends(get_db)):
    """Get a list of all league owners"""
    return db.query(models.User).all()

# --- 1. NEW: Get All Players (Fixes the ID numbers showing up) ---
@app.get("/players")
def get_players(db: Session = Depends(get_db)):
    return db.query(models.Player).all()

# --- 2. UPDATE: Get Draft History (Fixes the Debt) ---
# REPLACE the old "get_draft_history" function with this new strict one:
@app.get("/draft-history")
def get_draft_history(session_id: str, db: Session = Depends(get_db)):
    # STRICT FILTER: Only return picks that match the EXACT session ID
    # This prevents old history from ruining the budget
    return db.query(models.DraftPick).filter(models.DraftPick.session_id == session_id).all()

@app.get("/stats/top-spenders")
def get_top_spenders(db: Session = Depends(get_db)):
    """Who has spent the most money in league history?"""
    results = db.query(
        models.User.username, 
        func.sum(models.DraftPick.amount).label('total_spent')
    ).join(models.DraftPick).group_by(models.User.id).order_by(text("total_spent DESC")).all()
    
    return [{"owner": row.username, "total_spent": row.total_spent} for row in results]

# ---------------------------------------------------------
# DRAFT ACTIONS (This was missing!)
# ---------------------------------------------------------

# 1. Define the Data Model (The "Shape" of the data)
class DraftPickCreate(BaseModel):
    owner_id: int
    player_id: int  # <--- Strictly expecting an ID now
    amount: int
    session_id: str

# 2. The Draft Endpoint
@app.post("/draft-pick")
def draft_player(pick: DraftPickCreate, db: Session = Depends(get_db)):
    # A. Verify Player Exists
    player = db.query(models.Player).filter(models.Player.id == pick.player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found in database")

    # B. Check if already drafted in this session (Duplicate Check)
    existing_pick = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == pick.player_id,
        models.DraftPick.session_id == pick.session_id
    ).first()
    
    if existing_pick:
        raise HTTPException(status_code=400, detail="Player already drafted!")

    # C. Create the Draft Pick
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