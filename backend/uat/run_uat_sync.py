# backend/uat/run_uat_sync.py
from database import SessionLocal, engine
import models
from uat.seed_owners import seed_owners
from uat.seed_players import seed_players
from uat.seed_draft import seed_draft

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
    from uat.generate_matchups import run as generate_matchups
    generate_matchups()

    print("✨ UAT SYNC COMPLETE. Ready for testing.")
    db.close()

if __name__ == "__main__":
    run_uat()