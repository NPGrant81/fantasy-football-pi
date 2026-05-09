# backend/routers/auth.py
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

# 1.1.1 INFRASTRUCTURE: Use the new Security Core
from ..core import security
from .. import models
from ..schemas import User, UserCreate
from ..database import get_db
from ..services import rate_limiter_service

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


def _login_attempt_key(username: str, client_ip: str) -> str:
    return f"{client_ip}:{username.strip().lower()}"


def _is_rate_limited(key: str) -> bool:
    """Check if login attempt key is rate limited."""
    return rate_limiter_service.is_rate_limited(
        key,
        max_attempts=LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )


def _record_failed_attempt(key: str) -> None:
    """Record a failed login attempt."""
    rate_limiter_service.record_attempt(
        key,
        window_seconds=LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )


def _clear_failed_attempts(key: str) -> None:
    """Clear failed login attempts for a key (called on successful login)."""
    rate_limiter_service.clear_attempts(key)


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

    # 1.2.3 RETRIEVAL: Find the user (case-insensitive username match)
    user = db.query(models.User).filter(func.lower(models.User.username) == form_data.username.strip().lower()).first()
    
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
    logger.info("Successful login user_id=%s username=%s ip=%s", user.id, user.username, client_ip)
    security.prune_expired_revoked_tokens(db)

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
        "league_id": user.league_id,
        "is_commissioner": user.is_commissioner,
        "is_superuser": user.is_superuser,
        "division_id": user.division_id,
        "division_name": user.division_obj.name if user.division_obj else None,
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    token: str = Depends(security.oauth2_scheme),
    db: Session = Depends(get_db),
):
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    auth_token = security.choose_auth_token(cookie_token, token)
    if auth_token:
        security.revoke_access_token(db, auth_token)
        security.prune_expired_revoked_tokens(db)

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
        "is_superuser": current_user.is_superuser,
        "email": current_user.email,
        "division_id": current_user.division_id,
        "division_name": current_user.division_obj.name if current_user.division_obj else None,
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