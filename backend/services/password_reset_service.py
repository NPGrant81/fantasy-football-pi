"""
Password reset service for secure account recovery.

Implements secure password reset token generation, validation, and redemption
with anti-enumeration and single-use enforcement.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_
import importlib

# Import models with fallback
try:
    from backend.models import User, PasswordResetToken
except ImportError:
    models = importlib.import_module("backend.models")
    User = models.User
    PasswordResetToken = models.PasswordResetToken


def hash_reset_token(token: str) -> str:
    """
    Hash a password reset token using SHA-256.
    
    Args:
        token: Plain-text reset token (secrets.token_urlsafe(32))
    
    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(token.encode()).hexdigest()


def generate_reset_token() -> str:
    """
    Generate a secure password reset token.
    
    Returns:
        32 bytes of random data encoded in URL-safe base64 (~43 chars)
    """
    return secrets.token_urlsafe(32)


def create_password_reset_request(
    db: Session,
    user: User,
    client_ip: Optional[str] = None,
    expiry_minutes: int = 15,
) -> str:
    """
    Create a password reset token for a user.
    
    Issues a new reset token, saves its hash to the database, and returns
    the plain token (never stored in plaintext).
    
    Args:
        db: Database session
        user: User requesting password reset
        client_ip: IP address of the reset request (optional, for audit)
        expiry_minutes: Minutes until token expires (default: 15)
    
    Returns:
        Plain-text reset token (send to user via email)
    
    Raises:
        ValueError: If user is invalid or reset fails
    """
    if not user or not user.id:
        raise ValueError("Invalid user")

    # Serialize reset-token issuance per user to avoid concurrent multi-token races.
    db.query(User).filter(User.id == user.id).with_for_update().first()
    
    # Generate token
    token = generate_reset_token()
    token_hash = hash_reset_token(token)
    
    # Revoke any existing unused tokens for this user
    db.query(PasswordResetToken).filter(
        and_(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    ).delete()
    
    # Create new token record
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_ip=client_ip,
    )
    
    db.add(reset_token)
    db.commit()
    
    return token


def validate_and_use_reset_token(
    db: Session,
    user_id: int,
    token: str,
) -> bool:
    """
    Validate a reset token and mark it as used.
    
    Args:
        db: Database session
        user_id: User attempting to use the token
        token: Plain-text reset token from user
    
    Returns:
        True if token is valid and marked used
    
    Raises:
        ValueError: If token is invalid or already used
    """
    if not token or not user_id:
        raise ValueError("Invalid token or user_id")
    
    token_hash = hash_reset_token(token)
    now = datetime.now(timezone.utc)
    
    # Atomically mark token as used only if still valid and unused.
    updated = db.query(PasswordResetToken).filter(
        and_(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at >= now,
        )
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)

    if updated == 1:
        db.commit()
        return True

    # Resolve precise error for caller while preserving single-use semantics.
    reset_token = db.query(PasswordResetToken).filter(
        and_(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.user_id == user_id,
        )
    ).first()

    if not reset_token:
        raise ValueError("Token not found")

    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise ValueError("Token expired")

    if reset_token.used_at is not None:
        raise ValueError("Token already used")

    raise ValueError("Token not found")


def cleanup_expired_reset_tokens(db: Session) -> int:
    """
    Delete expired and used reset tokens.
    
    Called periodically to clean up old records. Only removes tokens that:
    - Have expired (expires_at < now)
    - Were used more than 1 hour ago
    
    Args:
        db: Database session
    
    Returns:
        Number of tokens deleted
    """
    now = datetime.now(timezone.utc)
    hour_ago = now - timedelta(hours=1)
    
    count = db.query(PasswordResetToken).filter(
        (PasswordResetToken.expires_at < now) |
        (and_(
            PasswordResetToken.used_at.isnot(None),
            PasswordResetToken.used_at < hour_ago,
        ))
    ).delete()
    
    db.commit()
    return count
