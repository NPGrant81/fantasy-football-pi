# backend/core/security.py
import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone # 1.1.1 Use timezone-aware datetime
from typing import Optional
from uuid import uuid4
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
# regardless of execution context, load backend modules explicitly to avoid
# duplicate metadata objects when SQLAlchemy reflects them under two names
import importlib

models = importlib.import_module("backend.models")
database = importlib.import_module("backend.database")


def _get_bcrypt_module():
    return importlib.import_module("bcrypt")

# alias get_db for dependency
get_db = database.get_db

# --- 1.1 CONFIGURATION ---
# 1.1.2 Ensure the app fails-fast if no secret key is provided in a real environment
SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_only_not_for_production")
APP_ENV = os.environ.get("APP_ENV", os.environ.get("ENVIRONMENT", "development")).lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}

if IS_PRODUCTION and SECRET_KEY == "dev_secret_only_not_for_production":
    raise RuntimeError("SECRET_KEY must be set to a strong value in production")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
ACCESS_TOKEN_COOKIE_NAME = os.environ.get("ACCESS_TOKEN_COOKIE_NAME", "ffpi_access_token")
ALLOW_BEARER_AUTH = os.environ.get("ALLOW_BEARER_AUTH", "0") == "1"
REVOCATION_PRUNE_INTERVAL_SECONDS = int(os.environ.get("REVOCATION_PRUNE_INTERVAL_SECONDS", "300"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "14"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# 1.1.3 IMPORTANT: Point this to your new auth router path
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)

# 1.1.4 Define a reusable credentials exception
credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

_last_revocation_prune_at: datetime | None = None

# --- 1.2 UTILITY FUNCTIONS (THE TOOLS) ---
def verify_password(plain_password, hashed_password):
    if not hashed_password:
        return False

    if isinstance(hashed_password, str) and hashed_password.startswith("$2"):
        try:
            bcrypt_module = _get_bcrypt_module()
            return bcrypt_module.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except ValueError:
            return False

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False
    except Exception:
        # Treat unknown/legacy hash formats as invalid credentials instead of 500.
        return False

def get_password_hash(password):
    # In tests we still return a valid bcrypt hash (lower cost) so accidental
    # persisted rows remain usable for auth instead of becoming permanent 401s.
    if os.getenv("TESTING") == "1" or os.getenv("PYTEST_CURRENT_TEST"):
        bcrypt_module = _get_bcrypt_module()
        return bcrypt_module.hashpw(password.encode("utf-8"), bcrypt_module.gensalt(rounds=4)).decode("utf-8")
    bcrypt_module = _get_bcrypt_module()
    return bcrypt_module.hashpw(password.encode("utf-8"), bcrypt_module.gensalt()).decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    # 1.2.1 Use timezone-aware UTC to prevent "Server Time" drift issues
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    if not to_encode.get("jti"):
        to_encode["jti"] = uuid4().hex

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token_record(
    db: Session,
    user_id: int,
    refresh_token: str,
    expires_at: datetime,
    rotated_from_token_hash: Optional[str] = None,
) -> models.RefreshToken:
    token_hash = hash_refresh_token(refresh_token)
    record = models.RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        rotated_from_token_hash=rotated_from_token_hash,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_refresh_token_record(db: Session, refresh_token: str) -> Optional[models.RefreshToken]:
    token_hash = hash_refresh_token(refresh_token)
    return (
        db.query(models.RefreshToken)
        .filter(models.RefreshToken.token_hash == token_hash)
        .first()
    )


def revoke_refresh_token(db: Session, refresh_token: str) -> bool:
    record = get_refresh_token_record(db, refresh_token)
    if record is None:
        return False
    if record.revoked_at is not None:
        return True

    record.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return True


def revoke_all_user_refresh_tokens(db: Session, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    updated = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.revoked_at.is_(None),
        )
        .update({models.RefreshToken.revoked_at: now}, synchronize_session=False)
    )
    if updated:
        db.commit()
    return int(updated)


def choose_auth_token(cookie_token: Optional[str], bearer_token: Optional[str]) -> Optional[str]:
    candidate_bearer = bearer_token if ALLOW_BEARER_AUTH else None
    return cookie_token or candidate_bearer


def decode_access_token(auth_token: str) -> dict:
    return jwt.decode(auth_token, SECRET_KEY, algorithms=[ALGORITHM])


def prune_expired_revoked_tokens(db: Session, force: bool = False) -> int:
    global _last_revocation_prune_at

    now = datetime.now(timezone.utc)
    if not force and _last_revocation_prune_at is not None:
        elapsed = (now - _last_revocation_prune_at).total_seconds()
        if elapsed < REVOCATION_PRUNE_INTERVAL_SECONDS:
            return 0

    deleted = (
        db.query(models.RevokedToken)
        .filter(models.RevokedToken.expires_at <= now)
        .delete(synchronize_session=False)
    )
    _last_revocation_prune_at = now
    if deleted:
        db.commit()
    return int(deleted)


def is_token_revoked(db: Session, jti: Optional[str]) -> bool:
    if not jti:
        return False
    return (
        db.query(models.RevokedToken.id)
        .filter(models.RevokedToken.jti == jti)
        .first()
        is not None
    )


def revoke_access_token(db: Session, auth_token: str) -> bool:
    try:
        payload = decode_access_token(auth_token)
    except JWTError:
        return False

    jti = payload.get("jti")
    exp = payload.get("exp")
    subject = payload.get("sub")
    if not jti or exp is None:
        return False

    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return False

    if is_token_revoked(db, jti):
        return True

    db.add(
        models.RevokedToken(
            jti=str(jti),
            token_subject=str(subject) if subject is not None else None,
            expires_at=expires_at,
        )
    )
    db.commit()
    return True

# --- 2.1 THE BOUNCERS (REFACTORED) ---

# --- 2.1 THE BOUNCERS (FIXED) ---

# 2.1.1 Standard User: Verifies token and returns the User object
async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    auth_token = choose_auth_token(cookie_token, token)
    if not auth_token:
        raise credentials_exception

    try:
        payload = decode_access_token(auth_token)
        username: str = payload.get("sub")
        jti: str | None = payload.get("jti")
        if username is None:
            raise credentials_exception
        # Check if token has been revoked (via logout or forced expiration)
        if jti:
            revoked = db.query(models.RevokedToken).filter(models.RevokedToken.jti == jti).first()
            if revoked:
                raise credentials_exception
    except JWTError:
        raise credentials_exception

    prune_expired_revoked_tokens(db)
    if is_token_revoked(db, jti):
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# 2.1.2 RENAMED: This matches your main.py import!
async def check_is_commissioner(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_commissioner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access denied. Commissioner privileges required."
        )
    return current_user

# 2.1.3 The Superuser Bouncer (Platform Admin)
async def get_current_active_superuser(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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


# --- 3.0 REFRESH TOKEN MANAGEMENT ---
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def _hash_token(token: str) -> str:
    """Hash a refresh token for secure storage."""
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


# Expose as public function for tests and external use
def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for secure storage (public interface)."""
    return _hash_token(token)


def generate_refresh_token() -> str:
    """Generate a secure refresh token."""
    import secrets
    return secrets.token_urlsafe(32)


def create_refresh_token_record(
    db: Session,
    user_id: int,
    refresh_token: str,
    expires_at: datetime,
    rotated_from_token_hash: str = None,
) -> models.RefreshToken:
    """Create a new refresh token record with optional rotation chain tracking."""
    token_hash = _hash_token(refresh_token)
    record = models.RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        rotated_from_token_hash=rotated_from_token_hash,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_refresh_token_record(db: Session, refresh_token: str) -> models.RefreshToken:
    """Retrieve a refresh token record by plain token (hashes it internally)."""
    token_hash = _hash_token(refresh_token)
    return db.query(models.RefreshToken).filter(
        models.RefreshToken.token_hash == token_hash
    ).first()


def revoke_all_user_refresh_tokens(db: Session, user_id: int) -> None:
    """Revoke all refresh tokens for a user (used during logout)."""
    now = datetime.now(timezone.utc)
    db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == user_id,
        models.RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": now})
    db.commit()


def revoke_access_token(db: Session, access_token: str) -> None:
    """Revoke an access token by storing its JTI in the blocklist."""
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            # Convert exp timestamp to datetime
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            existing = db.query(models.RevokedToken).filter(models.RevokedToken.jti == jti).first()
            if existing:
                return
            # Record the revocation
            revoked = models.RevokedToken(
                jti=jti,
                token_subject=payload.get("sub"),
                expires_at=expires_at,
            )
            db.add(revoked)
            try:
                db.commit()
            except IntegrityError:
                # Duplicate revoke attempts are safe to ignore.
                db.rollback()
    except (JWTError, ValueError):
        # Token is malformed or already expired, skip revocation
        pass


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    """Revoke a specific refresh token (mark as revoked)."""
    token_hash = _hash_token(refresh_token)
    now = datetime.now(timezone.utc)
    db.query(models.RefreshToken).filter(
        models.RefreshToken.token_hash == token_hash
    ).update({"revoked_at": now})
    db.commit()


def prune_expired_revoked_tokens(db: Session) -> None:
    """Clean up expired entries from both revoked_tokens and refresh_tokens tables."""
    now = datetime.now(timezone.utc)
    
    # Delete expired entries from revoked_tokens table
    db.query(models.RevokedToken).filter(
        models.RevokedToken.expires_at <= now
    ).delete()
    
    # Delete expired refresh tokens
    db.query(models.RefreshToken).filter(
        models.RefreshToken.expires_at <= now
    ).delete()
    
    db.commit()


def choose_auth_token(cookie_token: str, bearer_token: str) -> str:
    """Choose which token to use: cookie takes precedence over bearer token."""
    return cookie_token or bearer_token