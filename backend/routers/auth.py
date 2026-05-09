# backend/routers/auth.py
import logging
import os
import secrets
from datetime import timedelta
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
from ..services import password_reset_service

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
        logger.warning("Rate limited login attempt for user=%s ip=%s", form_data.username, client_ip)
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


# --- 2.4 ENDPOINT: PASSWORD RESET ---
class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


@router.post("/password-reset-request")
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Request a password reset token.
    
    Anti-enumeration: Returns 200 OK regardless of whether email exists.
    Only sends reset email if user account with that email exists.
    
    Returns: { "message": "If an account exists with this email, a reset link has been sent" }
    """
    email = payload.email.strip().lower() if payload.email else ""
    client_ip = request.client.host if request.client else None
    
    # Find user by email (case-insensitive)
    user = db.query(models.User).filter(
        func.lower(models.User.email) == email
    ).first()
    
    if user:
        try:
            # Generate reset token
            reset_token = password_reset_service.create_password_reset_request(
                db,
                user,
                client_ip=client_ip,
                expiry_minutes=15,
            )
            
            # TODO: Send email with reset link
            # reset_url = f"{os.getenv('FRONTEND_URL')}/reset-password?token={reset_token}&email={email}"
            # send_password_reset_email(user.email, reset_url)
            
            logger.info(
                "Password reset requested for user_id=%s email=%s ip=%s",
                user.id, email, client_ip,
            )
        except Exception as e:
            logger.error("Failed to create reset token for email=%s: %s", email, e)
    else:
        # Log non-existent email attempt (security monitoring)
        logger.warning("Password reset requested for non-existent email=%s ip=%s", email, client_ip)
    
    # Always return success (anti-enumeration)
    return {"message": "If an account exists with this email, a reset link has been sent"}


@router.post("/password-reset-confirm")
def confirm_password_reset(
    payload: PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Confirm password reset and set new password.
    
    Validates:
    - Token exists and hasn't expired
    - Token hasn't been used (single-use enforcement)
    - New password meets minimum requirements
    
    Returns: { "message": "Password reset successfully" }
    """
    token = payload.token.strip() if payload.token else ""
    new_password = payload.new_password.strip() if payload.new_password else ""
    client_ip = request.client.host if request.client else None
    
    if not token or not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token and new password are required",
        )
    
    # Validate password strength
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )
    
    # Find token in database
    token_hash = password_reset_service.hash_reset_token(token)
    reset_token = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token_hash == token_hash
    ).first()
    
    if not reset_token:
        logger.warning("Invalid password reset token attempted from ip=%s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    
    # Validate token
    try:
        password_reset_service.validate_and_use_reset_token(
            db, reset_token.user_id, token
        )
    except ValueError as e:
        logger.warning("Invalid reset token usage for user_id=%s: %s", reset_token.user_id, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    
    # Update user password
    user = reset_token.user
    user.hashed_password = security.get_password_hash(new_password)
    db.commit()
    
    logger.info(
        "Password reset confirmed for user_id=%s email=%s ip=%s",
        user.id, user.email, client_ip,
    )
    
    return {"message": "Password reset successfully"}