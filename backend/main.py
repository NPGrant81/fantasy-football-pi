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
        dashboard, players, waivers, draft, auth, feedback, trades, platform_tools, etl, nfl, playoffs
    )

load_dotenv()

app = FastAPI(title="Fantasy Football War Room API")


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
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS description VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS division_id INTEGER",  # added for divisions feature
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
# Note: create_all does not handle migrations. 
# Use Alembic if you add more columns later.
@app.on_event("startup")
async def startup_event():
    """Create database tables on app startup, not on import."""
    try:
        models.Base.metadata.create_all(bind=engine)
        ensure_runtime_schema()
    except Exception as e:
        print(f"Warning: Could not initialize database tables: {e}")

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

# PLATFORM TOOLS: Require superuser status
app.include_router(platform_tools.router)

# ADMIN TOOLS: commissioner‑level maintenance helpers (schedule import, etc.)
app.include_router(admin_tools.router)

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

# --- 4. THE AUTO-SEEDER ---
@app.on_event("startup")
def seed_database():
    db = SessionLocal()
    try:
        # Check for Admin User
        nick = db.query(models.User).filter(models.User.username == "Nick Grant").first()
        if not nick:
            print("Auto-Seeding: Creating Nick Grant...")
            nick = models.User(
                username="Nick Grant",
                email="nick@example.com",
                hashed_password=get_password_hash("password"), 
                is_commissioner=True,
                is_superuser=True,
                team_name="War Room Alpha"
            )
            db.add(nick)
            db.commit()
            db.refresh(nick)

        # Check for Default League
        test_league = db.query(models.League).filter(models.League.name == "The Big Show").first()
        if not test_league:
            print("Auto-Seeding: Creating 'The Big Show' League...")
            test_league = models.League(name="The Big Show")
            db.add(test_league)
            db.commit()
            db.refresh(test_league)
            
            # Link Nick to the new league
            nick.league_id = test_league.id
            db.commit()

        print("Auto-Seeding Complete.")
    except Exception as e:
        print(f"Seeding Error: {e}")
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Fantasy Football API is Running!"}