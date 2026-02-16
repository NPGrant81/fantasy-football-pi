# backend/routers/auth.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

# 1.1.1 INFRASTRUCTURE: Use the new Security Core
from core import security
import models
import schemas 
from database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])

# --- 2.1 ENDPOINT: REGISTRATION ---
@router.post("/register", response_model=schemas.User)
def register_user(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    # 1.2.1 VALIDATION: Check if username exists
    existing_user = db.query(models.User).filter(models.User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # 1.2.2 SECURITY: Hash the password (using the core security service)
    hashed_pw = security.get_password_hash(user_data.password)
    
    # 2.1.1 EXECUTION: Create and save the User
    new_user = models.User(
        username=user_data.username,
        hashed_password=hashed_pw,
        email=user_data.email,
        is_commissioner=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

# --- 2.2 ENDPOINT: LOGIN ---
@router.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1.2.3 RETRIEVAL: Find the user
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    # 1.2.4 VALIDATION: Verify password
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2.2.1 TOKEN GEN: Create JWT Access Token
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "owner_id": user.id,
        "league_id": user.league_id 
    }

# --- 2.3 ENDPOINT: IDENTITY ---
@router.get("/me")
def get_current_user_info(current_user: models.User = Depends(security.get_current_user)):
    return {
        "user_id": current_user.id, 
        "username": current_user.username,
        "league_id": current_user.league_id, 
        "is_commissioner": current_user.is_commissioner
    }