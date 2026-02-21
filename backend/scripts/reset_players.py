#!/usr/bin/env python
"""
Reset players: Delete all players and optionally reimport from ESPN.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine
import models

def reset_players():
    """Delete all players from the database."""
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        count = db.query(models.Player).count()
        print(f"Deleting {count} players...")
        db.query(models.Player).delete()
        db.commit()
        print(f"✅ Deleted all {count} players")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_players()
