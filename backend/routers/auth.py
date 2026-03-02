# backend/routers/auth.py
import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

# 1.1.1 INFRASTRUCTURE: Use the new Security Core
from ..core import security
from .. import models
from ..schemas import User, UserCreate
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])

logger = logging.getLogger(__name__)
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300"))
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "10"))
USE_COOKIE_AUTH = os.getenv("USE_COOKIE_AUTH", "1") != "0"
COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax")
COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "0") == "1"
ACCESS_TOKEN_COOKIE_NAME = security.ACCESS_TOKEN_COOKIE_NAME
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "ffpi_csrf_token")
CSRF_HEADER_NAME = os.getenv("CSRF_HEADER_NAME", "X-CSRF-Token")
failed_login_attempts: dict[str, deque[float]] = defaultdict(deque)
failed_login_lock = threading.Lock()


def _login_attempt_key(username: str, client_ip: str) -> str:
    return f"{client_ip}:{username.strip().lower()}"


def _trim_old_attempts(attempts: deque[float], now: float) -> None:
    cutoff = now - LOGIN_RATE_LIMIT_WINDOW_SECONDS
    while attempts and attempts[0] < cutoff:
        attempts.popleft()


def _is_rate_limited(key: str) -> bool:
    now = time.monotonic()
    with failed_login_lock:
        attempts = failed_login_attempts[key]
        _trim_old_attempts(attempts, now)
        return len(attempts) >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS


def _record_failed_attempt(key: str) -> None:
    now = time.monotonic()
    with failed_login_lock:
        attempts = failed_login_attempts[key]
        _trim_old_attempts(attempts, now)
        attempts.append(now)


def _clear_failed_attempts(key: str) -> None:
    with failed_login_lock:
        failed_login_attempts.pop(key, None)


def _is_secure_request(request: Request) -> bool:
    return COOKIE_SECURE or request.url.scheme == "https"


def _set_auth_cookies(response: Response, request: Request, access_token: str) -> None:
    secure_cookie = _is_secure_request(request)
    csrf_token = secrets.token_urlsafe(32)

    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=secure_cookie,
        samesite=COOKIE_SAMESITE,
        max_age=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=secure_cookie,
        samesite=COOKIE_SAMESITE,
        max_age=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")

# --- 2.1 ENDPOINT: REGISTRATION ---
@router.post("/register", response_model=User)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
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
def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    attempt_key = _login_attempt_key(form_data.username, client_ip)

    if _is_rate_limited(attempt_key):
        logger.warning("Rate-limited login attempt for user=%s ip=%s", form_data.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    # 1.2.3 RETRIEVAL: Find the user
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    # 1.2.4 VALIDATION: Verify password
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        _record_failed_attempt(attempt_key)
        logger.warning("Failed login attempt for user=%s ip=%s", form_data.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _clear_failed_attempts(attempt_key)
    
    # 2.2.1 TOKEN GEN: Create JWT Access Token
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    if USE_COOKIE_AUTH:
        _set_auth_cookies(response, request, access_token)
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "owner_id": user.id,
        "league_id": user.league_id 
    }


@router.post("/logout")
def logout(response: Response):
    _clear_auth_cookies(response)
    return {"message": "Logged out"}

# --- 2.3 ENDPOINT: IDENTITY ---
@router.get("/me")
def get_current_user_info(current_user: models.User = Depends(security.get_current_user)):
    return {
        "user_id": current_user.id, 
        "username": current_user.username,
        "league_id": current_user.league_id, 
        "is_commissioner": current_user.is_commissioner,
        "email": current_user.email
    }


class EmailUpdate(BaseModel):
    email: str


@router.put("/email")
def update_email(
    payload: EmailUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    email = payload.email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    current_user.email = email
    db.commit()
    db.refresh(current_user)

    return {"email": current_user.email}