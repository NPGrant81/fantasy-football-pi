from database import engine, SessionLocal
from sqlalchemy import text
import models
from passlib.context import CryptContext

def reset_database():
    print("🗑️  Resetting Database Schema (Nuclear Option)...")
    tables = ["budgets", "draft_picks", "matchups", "users", "players", "leagues", "league_settings"]
    with engine.connect() as connection:
        for table in tables:
            connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        connection.commit()
    print("✨ Recreating Tables...")
    models.Base.metadata.create_all(bind=engine)

def init_league():
    reset_database()
    db = SessionLocal()
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    print("⚙️  Initializing 'Post Pacific League'...")
    
    # 1. Create the LEAGUE Object (This was missing!)
    league = models.League(name="Post Pacific League")
    db.add(league)
    db.commit() # Commit to get the ID (should be 1)
    db.refresh(league)

    # 2. League Settings (Linked to name)
    complex_scoring = [
        {"cat": "Passing", "event": "Passing Yards", "min": 0, "max": 9999, "pts": 0.10, "type": "per_unit", "desc": "0.1 pts per yard"},
        {"cat": "Passing", "event": "Passing TD", "min": 0, "max": 99, "pts": 6, "type": "per_unit", "desc": "6 pts per TD"},
        {"cat": "Passing", "event": "Interceptions", "min": 0, "max": 999, "pts": -3, "type": "per_unit", "desc": "-3 per INT"},
        {"cat": "Rushing", "event": "Rushing Yards", "min": 0, "max": 9999, "pts": 0.30, "type": "per_unit", "desc": "0.3 pts per yard"},
        {"cat": "Rushing", "event": "Rushing TD", "min": 0, "max": 99, "pts": 10, "type": "per_unit", "desc": "10 pts per TD"},
        {"cat": "Receiving", "event": "Receiving Yards", "min": 0, "max": 9999, "pts": 0.30, "type": "per_unit", "desc": "0.3 pts per yard"},
        {"cat": "Receiving", "event": "Receptions", "min": 0, "max": 9999, "pts": 3, "type": "per_unit", "desc": "3 pts per catch"},
        {"cat": "Receiving", "event": "Receiving TD", "min": 0, "max": 99, "pts": 10, "type": "per_unit", "desc": "10 pts per TD"},
    ]

    settings = models.LeagueSettings(
        league_name="Post Pacific League",
        roster_size=14,
        salary_cap=200,
        starting_slots={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1, "FLEX": 1},
        scoring_rules=complex_scoring
    )
    db.add(settings)
    
    # 3. Create COMMISSIONER: Nick Grant
    print("👑 Creating Commissioner: Nick Grant...")
    me = models.User(
        username="Nick Grant", 
        email="nick@league.com",
        hashed_password=pwd_context.hash("password"),
        is_commissioner=True,
        league_id=league.id  # <--- ASSIGN TO LEAGUE
    )
    db.add(me)
    
    # 4. Create Placeholder Owners
    print("👥 Creating 11 Other Owners...")
    for i in range(1, 12):
        user = models.User(
            username=f"Owner_{i}",
            email=f"owner{i}@league.com",
            hashed_password=pwd_context.hash("password"),
            is_commissioner=False,
            league_id=league.id  # <--- ASSIGN TO LEAGUE
        )
        db.add(user)

    db.commit()
    print("✅ Post Pacific League (ID: 1) Initialized Successfully!")

if __name__ == "__main__":
    init_league()