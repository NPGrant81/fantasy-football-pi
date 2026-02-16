# backend/scripts/init_league.py
import sys
import os
from sqlalchemy import text
from datetime import datetime

# 1.1.1 Path Setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, SessionLocal, Base
import models
from core import security # 1.1.2 Use the professional core security module

def reset_db_schema():
    # 1.1.3 Postgres Nuclear Option (Keep your CASCADE logic)
    print("🗑️ Resetting Database Schema...")
    with engine.connect() as connection:
        with connection.begin():
            tables = ["matchups", "draft_picks", "league_settings", "scoring_rules", "players", "users", "leagues"]
            for table in tables:
                connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
    
    # 1.1.4 Rebuild tables from models
    Base.metadata.create_all(bind=engine)

def seed_data():
    db = SessionLocal()
    try:
        # 2.1 CREATE LEAGUE
        print("⚙️ Initializing 'Post Pacific League'...")
        league = models.League(name="Post Pacific League", draft_status="PRE_DRAFT")
        db.add(league)
        db.commit()
        db.refresh(league)

        # 2.2 CREATE SUPERUSER (Using Core Security)
        print("👑 Creating Commissioner: Nick Grant...")
        hashed_pw = security.get_password_hash("password")
        admin = models.User(
            username="Nick_Grant",
            email="nick@league.com",
            hashed_password=hashed_pw,
            is_superuser=True,
            is_commissioner=True,
            league_id=league.id
        )
        db.add(admin)

        # 2.3 LOAD SCORING RULES
        # (Include your initial_rules list from your previous init_league file here)
        
        db.commit()
        print("✅ League and Superuser initialized successfully!")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_db_schema()
    seed_data()