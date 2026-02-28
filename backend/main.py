import os
import sys
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
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
    analytics = importlib.import_module("backend.routers.analytics")

    engine = dbmod.engine
    SessionLocal = dbmod.SessionLocal
    get_password_hash = secmod.get_password_hash
    check_is_commissioner = secmod.check_is_commissioner
else:
    # normal package imports
    from . import models
    from .database import engine, SessionLocal
    from .core.security import get_password_hash, check_is_commissioner
    from .routers import (
        admin, admin_tools, team, matchups, league, advisor,
        dashboard, players, waivers, draft, auth, feedback, trades, platform_tools, etl, nfl, playoffs, analytics, keepers
    )

load_dotenv()

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
        models.Base.metadata.create_all(bind=engine)
        ensure_runtime_schema()
    except Exception as e:
        print(f"Warning: Could not initialize database tables: {e}")

    yield

    # --- shutdown portion ---
    # (currently nothing to clean up here; kept for future use)

app = FastAPI(title="Fantasy Football War Room API", lifespan=lifespan)


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
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS playoff_tiebreakers JSON DEFAULT '[\"points_for\",\"head_to_head\",\"division_wins\",\"wins\"]'",
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS future_draft_cap INTEGER DEFAULT 0",  # required by ORM
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS description VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS division_id INTEGER",  # added for divisions feature
        # new field added in recent schema; seeding logic expects it
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS future_draft_budget INTEGER DEFAULT 0",
        # taxi support: mark picks that aren’t eligible for starting lineup
        "ALTER TABLE draft_picks ADD COLUMN IF NOT EXISTS is_taxi BOOLEAN DEFAULT FALSE",
        # keeper feature additions
        "ALTER TABLE keeper_rules ADD COLUMN IF NOT EXISTS max_years_per_player INTEGER DEFAULT 1",
        "ALTER TABLE keepers ADD COLUMN IF NOT EXISTS years_kept_count INTEGER DEFAULT 1",
        "ALTER TABLE keepers ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE keepers ADD COLUMN IF NOT EXISTS approved_by_commish BOOLEAN DEFAULT FALSE",
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
allowed = ["*"] if os.getenv("ALLOW_ALL_ORIGINS") == "1" else [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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