import sys
import os
from sqlalchemy import text

# 1. Setup path to import from backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 2. Import your specific Database setup
from database import engine, SessionLocal, Base
import models
from auth import get_password_hash 

def reset_database_schema():
    """
    The 'Nuclear Option' for PostgreSQL.
    Drops all tables and types to ensure a clean slate.
    """
    print("🗑️  Resetting Database Schema (Postgres Nuclear Option)...")
    
    # List all your tables here to ensure they are wiped
    # ORDER MATTERS: Drop children (Matchups) before parents (Users)
    tables = [
        "matchups", "draft_picks", "budgets", "teams", 
        "league_settings", "scoring_rules", "players", 
        "users", "leagues"
    ]
    
    with engine.connect() as connection:
        with connection.begin(): # Start a transaction
            # A. Drop Tables
            for table in tables:
                try:
                    # CASCADE is crucial for Postgres foreign keys
                    connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
                    print(f"   - Dropped table: {table}")
                except Exception as e:
                    print(f"   ⚠️ Warning dropping {table}: {e}")
            
            # B. Drop the ENUM Type (Postgres specific)
            # This prevents "type userrole already exists" errors on restart
            try:
                connection.execute(text("DROP TYPE IF EXISTS userrole CASCADE;"))
                print("   - Dropped Enum Type: userrole")
            except Exception as e:
                # It's okay if it fails (means it didn't exist yet)
                pass

    print("✨ Recreating Tables from Models...")
    # This reads your models.py and builds the new schema
    Base.metadata.create_all(bind=engine)

def init_league():
    # 1. WIPE AND REBUILD
    reset_database_schema()
    
    db = SessionLocal()

    try:
        print("\n⚙️  Initializing 'Post Pacific League'...")
        
        # 2. CREATE LEAGUE
        league = models.League(name="Post Pacific League")
        db.add(league)
        db.commit()
        db.refresh(league)

        # 3. LOAD SCORING RULES
        # These are the default rules for your league
        print("📊 Loading Scoring Rules...")
        initial_rules = [
            # -- Volume Rules --
            {"cat": "PASSING_YARDS", "min": 0, "max": 9999, "pts": 0.10, "pos": None},
            {"cat": "PASSING_TD", "min": 0, "max": 99, "pts": 6.0, "pos": None},
            {"cat": "INTERCEPTION", "min": 0, "max": 999, "pts": -3.0, "pos": None},
            {"cat": "RUSHING_YARDS", "min": 0, "max": 9999, "pts": 0.30, "pos": None},
            {"cat": "RUSHING_TD", "min": 0, "max": 99, "pts": 10.0, "pos": None},
            {"cat": "RECEIVING_YARDS", "min": 0, "max": 9999, "pts": 0.30, "pos": None},
            {"cat": "RECEPTIONS", "min": 0, "max": 9999, "pts": 3.0, "pos": None},
            {"cat": "RECEIVING_TD", "min": 0, "max": 99, "pts": 10.0, "pos": None},
            
            # -- Complex/Bonus Rules --
            {"cat": "PASSING_TD_LENGTH", "min": 40, "max": 49, "pts": 2.0, "pos": "QB"},
            {"cat": "RUSHING_YARDS_GAME", "min": 100, "max": 109, "pts": 5.0, "pos": None},
        ]

        for r in initial_rules:
            new_rule = models.ScoringRule(
                league_id=league.id,
                category=r["cat"],
                min_val=r["min"],
                max_val=r["max"],
                points=r["pts"],
                position_target=r["pos"]
            )
            db.add(new_rule)

        # 4. LEAGUE SETTINGS
        settings = models.LeagueSettings(
            league_id=league.id,
            league_name="Post Pacific League",
            roster_size=14,
            salary_cap=200,
            starting_slots={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1, "FLEX": 1}
        )
        db.add(settings)

        # 5. ADMIN USER (You)
        print("👑 Creating Commissioner: Nick Grant...")
        me = models.User(
            username="Nick Grant",
            email="nick@league.com",
            hashed_password=get_password_hash("password"), # Matches auth.py
            role=models.UserRole.ADMIN, # The new Enum Role
            is_commissioner=True,
            league_id=league.id,
            division="North"
        )
        db.add(me)

        # 6. DUMMY OWNERS (For Testing)
        print("👥 Creating 11 Other Owners...")
        for i in range(1, 12):
            user = models.User(
                username=f"Owner_{i}",
                email=f"owner{i}@league.com",
                hashed_password=get_password_hash("password"),
                role=models.UserRole.USER,
                league_id=league.id,
                division="South" if i > 5 else "North"
            )
            db.add(user)

        db.commit()
        print(f"✅ Post Pacific League (ID: {league.id}) Initialized Successfully!")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_league()
