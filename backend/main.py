import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy import text

# Internal Imports
import models
from database import engine, SessionLocal
from core.security import get_password_hash, check_is_commissioner

# Import All Routers
from routers import (
    admin, team, matchups, league, advisor,
    dashboard, players, waivers, draft, auth, feedback, trades, platform_tools, etl
)

load_dotenv()

app = FastAPI(title="Fantasy Football War Room API")


def ensure_runtime_schema() -> None:
    """Apply minimal non-destructive schema fixes required by active routes."""
    statements = [
        "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS draft_year INTEGER",
        "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS description VARCHAR",
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

# STANDARD: Included without redundant prefixes
app.include_router(auth.router)
app.include_router(draft.router)
app.include_router(team.router)
app.include_router(matchups.router)
app.include_router(league.router)
app.include_router(advisor.router)
app.include_router(dashboard.router)
app.include_router(players.router) 
app.include_router(waivers.router)
app.include_router(trades.router)
app.include_router(feedback.router)
app.include_router(etl.router)

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