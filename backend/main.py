import os
import sys
import logging
from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from dotenv import load_dotenv
from sqlalchemy import text

# fix package context when running from backend/ directory
# (e.g. `uvicorn main:app` instead of `uvicorn backend.main:app`).
# We also handle script mode by importing every symbol via importlib so that
# modules are always loaded as `backend.xxx`.  Detection starts by checking
# whether the module is executed as __main__ or has no package name.
if __name__ == "__main__" or __package__ in (None, ""):
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(pkg_dir)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    # import everything explicitly from backend so module name is correct
    import importlib
    backend_pkg = importlib.import_module("backend")
    models = importlib.import_module("backend.models")
    dbmod = importlib.import_module("backend.database")
    secmod = importlib.import_module("backend.core.security")
    # load routers package and each submodule explicitly
    routers_pkg = importlib.import_module("backend.routers")
    # the package itself may not yet have attributes for each router, so import
    # them individually and bind to names below
    admin = importlib.import_module("backend.routers.admin")
    admin_tools = importlib.import_module("backend.routers.admin_tools")
    team = importlib.import_module("backend.routers.team")
    matchups = importlib.import_module("backend.routers.matchups")
    league = importlib.import_module("backend.routers.league")
    advisor = importlib.import_module("backend.routers.advisor")
    dashboard = importlib.import_module("backend.routers.dashboard")
    players = importlib.import_module("backend.routers.players")
    waivers = importlib.import_module("backend.routers.waivers")
    draft = importlib.import_module("backend.routers.draft")
    auth = importlib.import_module("backend.routers.auth")
    feedback = importlib.import_module("backend.routers.feedback")
    trades = importlib.import_module("backend.routers.trades")
    platform_tools = importlib.import_module("backend.routers.platform_tools")
    etl = importlib.import_module("backend.routers.etl")
    nfl = importlib.import_module("backend.routers.nfl")
    playoffs = importlib.import_module("backend.routers.playoffs")
    analytics = importlib.import_module("backend.routers.analytics")
    keepers = importlib.import_module("backend.routers.keepers")
    divisions = importlib.import_module("backend.routers.divisions")
    scoring = importlib.import_module("backend.routers.scoring")
    analytics = importlib.import_module("backend.routers.analytics")

    engine = dbmod.engine
    SessionLocal = dbmod.SessionLocal
    get_password_hash = secmod.get_password_hash
    check_is_commissioner = secmod.check_is_commissioner
    watchdog_service = importlib.import_module("backend.services.live_scoring_watchdog_service")
    run_seeder = importlib.import_module("backend.scripts.seed").run_seeder
else:
    # normal package imports
    from . import models
    from .database import engine, SessionLocal
    from .core.security import get_password_hash, check_is_commissioner
    from .services import live_scoring_watchdog_service as watchdog_service
    from .scripts.seed import run_seeder
    from .routers import (
        admin, admin_tools, team, matchups, league, advisor,
        dashboard, players, waivers, draft, auth, feedback, trades, platform_tools, etl, nfl, playoffs, analytics, keepers, divisions, scoring
    )

load_dotenv()

logger = logging.getLogger(__name__)


def _advisor_runtime_status() -> dict[str, bool | str]:
    has_gemini_key = bool(os.getenv("GEMINI_API_KEY"))
    has_google_key = bool(os.getenv("GOOGLE_API_KEY"))
    has_api_key = has_gemini_key or has_google_key
    has_genai_sdk = bool(getattr(advisor, "genai", None))

    key_source = "none"
    if has_google_key:
        key_source = "GOOGLE_API_KEY"
    elif has_gemini_key:
        key_source = "GEMINI_API_KEY"

    return {
        "enabled": has_api_key and has_genai_sdk,
        "has_api_key": has_api_key,
        "has_genai_sdk": has_genai_sdk,
        "key_source": key_source,
    }

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager takes the place of startup/shutdown events.

    Tables are created and runtime schema fixes applied before the
    application starts accepting requests.  This guarantees ordering and
    avoids races that were causing intermittent connection errors in CI.
    """
    # --- startup portion ---
    try:
        # run any pending alembic migrations on startup so the schema stays
        # up‑to‑date even if somebody applied a migration externally (e.g. via
        # a cron job or manual `alembic upgrade`).  this is lightweight and
        # idempotent.
        from alembic import command, config as alembic_config
        cfg = alembic_config.Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
        command.upgrade(cfg, "heads")
    except Exception as e:
        # if the DB isn't reachable or alembic isn't configured, we just
        # log and continue.  the runtime schema function will still patch
        # whatever it can.
        print(f"Warning: alembic upgrade step failed: {e}")

    try:
        models.Base.metadata.create_all(bind=engine)
        ensure_runtime_schema()
    except Exception as e:
        print(f"Warning: Could not initialize database tables: {e}")

    try:
        auto_seed = os.getenv("AUTO_SEED_ON_STARTUP", "1")
        app_env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
        if auto_seed == "1" and app_env not in {"production", "prod"}:
            run_seeder(SessionLocal, get_password_hash)
    except Exception as e:
        print(f"Warning: Could not run startup seeder: {e}")

    advisor_status = _advisor_runtime_status()
    logger.info(
        "Advisor runtime status enabled=%s has_api_key=%s has_genai_sdk=%s key_source=%s",
        advisor_status["enabled"],
        advisor_status["has_api_key"],
        advisor_status["has_genai_sdk"],
        advisor_status["key_source"],
    )

    try:
        watchdog_service.start_live_scoring_watchdog_scheduler()
    except Exception as e:
        print(f"Warning: Could not start live scoring watchdog scheduler: {e}")

    yield

    # --- shutdown portion ---
    # (currently nothing to clean up here; kept for future use)
    try:
        watchdog_service.stop_live_scoring_watchdog_scheduler()
    except Exception as e:
        print(f"Warning: Could not stop live scoring watchdog scheduler: {e}")

app = FastAPI(title="Fantasy Football War Room API", lifespan=lifespan)

ACCESS_TOKEN_COOKIE_NAME = os.getenv("ACCESS_TOKEN_COOKIE_NAME", "ffpi_access_token")
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "ffpi_csrf_token")
CSRF_HEADER_NAME = os.getenv("CSRF_HEADER_NAME", "X-CSRF-Token")
CSRF_EXEMPT_PATHS = {
    "/auth/token",
    "/analytics/visit",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


def _parse_csv_env(env_var: str, default_values: list[str]) -> list[str]:
    raw = os.getenv(env_var)
    if not raw:
        return default_values
    return [value.strip() for value in raw.split(",") if value.strip()]


def ensure_runtime_schema() -> None:
    """Apply minimal non-destructive schema fixes required by active routes."""
    # When new columns are added to tables but upstream migrations may not have
    # been run, we pragmatically add them here so the app can start without
    # blowing up.  This isn't a substitute for Alembic in production, but it
    # keeps local dev and UAT scripts from crashing.
    statements = [
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS draft_year INTEGER",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS trade_deadline VARCHAR",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS starting_waiver_budget INTEGER DEFAULT 100",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS waiver_system VARCHAR",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS waiver_tiebreaker VARCHAR",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS playoff_qualifiers INTEGER DEFAULT 6",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS playoff_reseed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS playoff_consolation BOOLEAN DEFAULT TRUE",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS playoff_tiebreakers JSON DEFAULT '[\"overall_record\",\"head_to_head\",\"points_for\",\"points_against\",\"random_draw\"]'",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS future_draft_cap INTEGER DEFAULT 0",  # required by ORM
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS divisions_enabled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS division_count INTEGER",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS division_config_status VARCHAR DEFAULT 'draft'",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS division_assignment_method VARCHAR",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS division_random_seed VARCHAR",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS division_needs_reseed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS division_history_enabled BOOLEAN DEFAULT TRUE",
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS season_year INTEGER",
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS description VARCHAR",
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS position_ids JSON DEFAULT '[]'",
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS source VARCHAR(32) DEFAULT 'custom'",
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS template_id INTEGER",
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER",
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS updated_by_user_id INTEGER",
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS division_id INTEGER",  # added for divisions feature
        "ALTER TABLE divisions ADD COLUMN IF NOT EXISTS season INTEGER",
        "ALTER TABLE divisions ADD COLUMN IF NOT EXISTS order_index INTEGER DEFAULT 0",
        # new field added in recent schema; seeding logic expects it
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS future_draft_budget INTEGER DEFAULT 0",
        # taxi support: mark picks that aren’t eligible for starting lineup
        "ALTER TABLE draft_picks ADD COLUMN IF NOT EXISTS is_taxi BOOLEAN DEFAULT FALSE",
        # keeper feature additions
        "ALTER TABLE keeper_rules ADD COLUMN IF NOT EXISTS max_years_per_player INTEGER DEFAULT 1",
        "ALTER TABLE keepers ADD COLUMN IF NOT EXISTS years_kept_count INTEGER DEFAULT 1",
        "ALTER TABLE keepers ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE keepers ADD COLUMN IF NOT EXISTS approved_by_commish BOOLEAN DEFAULT FALSE",
        "ALTER TABLE matchups ADD COLUMN IF NOT EXISTS is_division_matchup BOOLEAN DEFAULT FALSE",
        "ALTER TABLE matchups ADD COLUMN IF NOT EXISTS is_rivalry_week BOOLEAN DEFAULT FALSE",
        "ALTER TABLE matchups ADD COLUMN IF NOT EXISTS rivalry_name VARCHAR",
        "ALTER TABLE playoff_matches ADD COLUMN IF NOT EXISTS team_1_seed INTEGER",
        "ALTER TABLE playoff_matches ADD COLUMN IF NOT EXISTS team_2_seed INTEGER",
        "ALTER TABLE playoff_matches ADD COLUMN IF NOT EXISTS team_1_is_division_winner BOOLEAN DEFAULT FALSE",
        "ALTER TABLE playoff_matches ADD COLUMN IF NOT EXISTS team_2_is_division_winner BOOLEAN DEFAULT FALSE",
        # draft_values extended stats — computed from draft_picks (no CSV import)
        "ALTER TABLE draft_values ADD COLUMN IF NOT EXISTS avg_bid FLOAT",
        "ALTER TABLE draft_values ADD COLUMN IF NOT EXISTS median_bid FLOAT",
        "ALTER TABLE draft_values ADD COLUMN IF NOT EXISTS recent_3yr_avg FLOAT",
        "ALTER TABLE draft_values ADD COLUMN IF NOT EXISTS trend_slope FLOAT",
        "ALTER TABLE draft_values ADD COLUMN IF NOT EXISTS appearances INTEGER",
        "ALTER TABLE draft_values ADD COLUMN IF NOT EXISTS model_score FLOAT",
        "ALTER TABLE draft_values ADD COLUMN IF NOT EXISTS rank INTEGER",
    ]

    with engine.connect() as connection:
        for statement in statements:
            try:
                connection.execute(text(statement))
                connection.commit()
            except Exception as exc:
                connection.rollback()
                print(f"Warning: Could not apply runtime schema fix ({statement}): {exc}")

# --- 1. DATABASE SETUP ---
# The database initialization logic has been moved into the lifespan
# manager above.  We no longer use an `@app.on_event("startup")` handler
# because lifespan provides a more reliable ordering and allows tests to
# bypass the routine when desired.
# --- 2. SECURITY: CORS ---
# Allow development origins; when running locally we accept any origin to
# simplify front-end testing.  In production this should be locked down.
allowed_hosts = _parse_csv_env("ALLOWED_HOSTS", ["localhost", "127.0.0.1", "testserver"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

allowed = ["*"] if os.getenv("ALLOW_ALL_ORIGINS") == "1" else _parse_csv_env(
    "FRONTEND_ALLOWED_ORIGINS",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    is_unsafe_method = request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
    is_exempt_path = request.url.path in CSRF_EXEMPT_PATHS or request.url.path.startswith("/docs")

    if is_unsafe_method and not is_exempt_path:
        cookie_access_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
        auth_header = request.headers.get("Authorization", "")
        uses_cookie_auth = bool(cookie_access_token) and not auth_header.lower().startswith("bearer ")

        if uses_cookie_auth:
            csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
            csrf_header = request.headers.get(CSRF_HEADER_NAME)
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token validation failed"},
                )

    response = await call_next(request)

    security_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Content-Security-Policy": os.getenv(
            "CONTENT_SECURITY_POLICY",
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
            "connect-src 'self' http://localhost:5173 http://127.0.0.1:5173 https:; font-src 'self' data:",
        ),
    }

    for header_name, header_value in security_headers.items():
        if header_name not in response.headers:
            response.headers[header_name] = header_value

    if request.url.scheme == "https" and "Strict-Transport-Security" not in response.headers:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response

# --- 3. CONNECT ROUTERS ---
# We remove 'prefix' here because your individual router files 
# (e.g., auth.py, team.py) should define them internally.

# PROTECTED: Admin requires Commissioner status
app.include_router(
    admin.router, 
    dependencies=[Depends(check_is_commissioner)] 
)
# analytics endpoints are public to league members (authorization can be added later)
app.include_router(analytics.router)
# ADMIN TOOLS: commissioner‑level maintenance helpers (schedule import, etc.)
app.include_router(admin_tools.router)

# PLATFORM TOOLS: superuser endpoints such as commissioner management
# (must match prefix set in routers/platform_tools.py)
# 404 errors seen in CI tests were due to forgetting this include or
# using a mismatched path.  If you add routes here, double‑check the
# decorator paths and prefix.
app.include_router(platform_tools.router)

# STANDARD: Included without redundant prefixes
app.include_router(auth.router)
app.include_router(draft.router)
app.include_router(team.router)
app.include_router(matchups.router)
app.include_router(league.router)
app.include_router(divisions.router)
app.include_router(playoffs.router)  # new playoff endpoints
app.include_router(advisor.router)
app.include_router(dashboard.router)
app.include_router(players.router) 
app.include_router(waivers.router)
app.include_router(trades.router)
app.include_router(feedback.router)
app.include_router(etl.router)
app.include_router(nfl.router)
app.include_router(keepers.router)
app.include_router(scoring.router)

# --- 4. SEEDER (moved) ---
# The automatic seeding logic used to live here but caused every test that
# imported ``app`` to execute the full seeder.  It has been extracted into
# a standalone command-line helper; run ``python -m backend.manage seed``
# when you want to populate a new database.  This keeps TestClient from
# unintentionally hitting the seeder and avoids mysterious ``db``
# NameErrors.

@app.get("/")
def read_root():
    return {"message": "Fantasy Football API is Running!"}


@app.get("/health")
def health_check():
    db_ok = True
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
        # Keep full exception details in server logs only.
        logger.exception("Health check DB probe failed")

    payload = {
        "status": "ok" if db_ok else "degraded",
        "service": "fantasy-football-backend",
        "database": "ok" if db_ok else "error",
    }
    if db_ok:
        return payload
    return JSONResponse(status_code=503, content=payload)