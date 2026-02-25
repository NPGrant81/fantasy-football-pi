# backend/uat/run_uat_sync.py
# Ensure parent path is in sys.path so `backend` package can be imported
import os, sys
if __package__ in (None, ""):
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(pkg_dir)
    if parent not in sys.path:
        sys.path.insert(0, parent)

# always import via backend package name only
from backend.database import SessionLocal, engine
from backend import models
from backend.uat.seed_owners import seed_owners
from backend.uat.seed_players import seed_players
from backend.uat.seed_draft import seed_draft

def run_uat():
    db = SessionLocal()
    print("🚀 STARTING FULL UAT SYNC...")
    
    # 2.1 EXECUTION: Atomic Wipe & Sequential Seeding
    print("🧹 Cleaning database...")
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    
    seed_owners(db)
    seed_players(db)
    seed_draft(db)

    # Always generate matchups after seeding
    from backend.uat.generate_matchups import run as generate_matchups
    generate_matchups()

    print("✨ UAT SYNC COMPLETE. Ready for testing.")
    db.close()

if __name__ == "__main__":
    run_uat()