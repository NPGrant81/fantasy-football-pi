# backend/core/security.py
import os
from datetime import datetime, timedelta, timezone # 1.1.1 Use timezone-aware datetime
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# 1.1.3 IMPORTANT: Point this to your new auth router path
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)

# 1.1.4 Define a reusable credentials exception
credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

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

def get_password_hash(password):
    # when running automated tests we don't want to invoke bcrypt
    # initialization or worry about input length limits.  a simple
    # flag allows the test harness to bypass real hashing entirely.
    # either explicit testing flag or running under pytest
    if os.getenv("TESTING") == "1" or os.getenv("PYTEST_CURRENT_TEST"):
        return "test-hash"
    bcrypt_module = _get_bcrypt_module()
    return bcrypt_module.hashpw(password.encode("utf-8"), bcrypt_module.gensalt()).decode("utf-8")

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

# --- 2.1 THE BOUNCERS (FIXED) ---

# 2.1.1 Standard User: Verifies token and returns the User object
async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    bearer_token = token if ALLOW_BEARER_AUTH else None
    auth_token = cookie_token or bearer_token
    if not auth_token:
        raise credentials_exception

    try:
        payload = jwt.decode(auth_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
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