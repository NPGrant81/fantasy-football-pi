from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from models import User
from sqlalchemy.orm import Session
import os
import models
from database import get_db, SessionLocal

# SECRET KEY (In production, load this from .env)
SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def check_is_commissioner(current_user: User = Depends(get_current_active_user)):
    """
    Checks if the authenticated user has commissioner privileges.
    If not, it raises a 403 Forbidden error immediately.
    """
    if not current_user.is_commissioner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Commissioner privileges required."
        )
    return current_user

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    """
    Spartan check to ensure the user exists and is active.
    """
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return current_user

def check_is_commissioner(current_user: models.User = Depends(get_current_active_user)):
    """
    The 'Gold Plating' security gate.
    Checks the Boolean flag we set in our seeder.
    """
    if not current_user.is_commissioner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Commissioner privileges required."
        )
    return current_user

# If you still want an 'Admin' specific check for superusers:
async def get_current_active_admin(current_user: models.User = Depends(get_current_active_user)):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Superuser privileges required"
        )
    return current_user

async def get_current_active_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin" and current_user.role != "commish":
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user