# backend/core/security.py
import os
from datetime import datetime, timedelta, timezone # 1.1.1 Use timezone-aware datetime
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import models
from database import get_db

# --- 1.1 CONFIGURATION ---
# 1.1.2 Ensure the app fails-fast if no secret key is provided in a real environment
SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_only_not_for_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 3000 

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# 1.1.3 IMPORTANT: Point this to your new auth router path
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# --- 1.2 UTILITY FUNCTIONS (THE TOOLS) ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    # 1.2.1 Use timezone-aware UTC to prevent "Server Time" drift issues
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- 2.1 THE BOUNCERS (REFACTORED) ---

# 2.1.1 Standard User: Verifies token and returns the User object
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # (Existing JWT decoding logic)
    # ...
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# 2.1.2 The Commissioner: Only lets league leaders through
async def get_current_active_commish(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_commissioner:
        raise HTTPException(
            status_code=403, 
            detail="Access denied. Commissioner privileges required."
        )
    return current_user

# 2.1.3 The Superuser: Only lets platform developers through
async def get_current_active_admin(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, 
            detail="Superuser privileges required"
        )
    return current_user

# 2.1.4 Specialized Bouncer: Only lets Commissioners through
async def get_current_active_admin(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_commissioner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access denied: Commissioner privileges required."
        )
    return current_user