import os
import warnings
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


DEFAULT_DB_URL = "postgresql://localhost/fantasy_football"


def load_backend_env_file() -> None:
    backend_dir = Path(__file__).resolve().parent
    # Load only backend/.env to avoid surprising CWD-based .env resolution.
    load_dotenv(backend_dir / ".env", override=False)


def is_credentialless_local_postgres(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme.startswith("postgres") and parsed.username is None and host in {"", "localhost", "127.0.0.1"}


def resolve_database_url(*, require_explicit: bool, context: str) -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        database_url = configured
    elif require_explicit:
        raise RuntimeError(
            "DATABASE_URL is required. Copy backend/.env.example to backend/.env and set DATABASE_URL "
            f"before running {context}."
        )
    else:
        warnings.warn(
            "DATABASE_URL is not set; falling back to local Postgres URL without credentials. "
            "Copy backend/.env.example to backend/.env and set DATABASE_URL for reliable local runtime.",
            RuntimeWarning,
            stacklevel=2,
        )
        database_url = DEFAULT_DB_URL

    if is_credentialless_local_postgres(database_url):
        warnings.warn(
            "DATABASE_URL points at local Postgres without embedded credentials; auth may fail unless trust auth is configured. "
            "Use backend/.env with a credentialed DSN for consistent local behavior.",
            RuntimeWarning,
            stacklevel=2,
        )

    return database_url
