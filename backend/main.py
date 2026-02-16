from fastapi import FastAPI, Depends, CORSMiddleware  # Added Depends
from dotenv import load_dotenv

# Internal Imports
import models
from database import engine, SessionLocal
from auth import get_password_hash, check_is_commissioner # Cleaned up imports

# Import All Routers
from routers import admin, team, matchups, league, advisor, dashboard, players, waivers, draft, auth

# Load Environment Variables
load_dotenv()

# --- 1. DATABASE SETUP ---
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- 2. SECURITY: CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 3. CONNECT ROUTERS ---

# PROTECTED: Admin requires Commissioner status
app.include_router(
    admin.router, 
    prefix="/admin", 
    tags=["Admin"],
    dependencies=[Depends(check_is_commissioner)] 
)

# STANDARD: Grouped with prefixes
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(draft.router, prefix="/draft", tags=["Draft"])
app.include_router(team.router, prefix="/team", tags=["Team"])
app.include_router(matchups.router, prefix="/matchups", tags=["Matchups"])
app.include_router(league.router, prefix="/league", tags=["League"])
app.include_router(advisor.router, prefix="/advisor", tags=["Advisor"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(players.router, prefix="/players", tags=["Players"]) 
app.include_router(waivers.router, prefix="/waivers", tags=["Waivers"])

# --- 4. THE AUTO-SEEDER ---
@app.on_event("startup")
def seed_database():
    db = SessionLocal()
    try:
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

        test_league = db.query(models.League).filter(models.League.name == "The Big Show").first()
        if not test_league:
            print("Auto-Seeding: Creating 'The Big Show' League...")
            test_league = models.League(name="The Big Show")
            db.add(test_league)
            db.commit()
            db.refresh(test_league)
            
            nick.league_id = test_league.id
            db.commit()

        print("Auto-Seeding Complete.")
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Fantasy Football API is Running!"}