import random
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models

# 1. Initialize DB & CREATE MISSING TABLES
# This line is crucial because we just dropped the table!
models.Base.metadata.create_all(bind=engine)

db = SessionLocal()

def seed_draft():
    print("🎲 SEEDING DRAFT: Fast-Forwarding to Season Start...")

    # --- A. CLEAN SLATE ---
    print("   - Clearing existing draft picks...")
    try:
        db.query(models.DraftPick).delete()
        db.commit()
    except Exception as e:
        print(f"   - Table might be new, skipping delete. ({e})")
        db.rollback()

    # --- B. GET OWNERS & PLAYERS ---
    # Get all human owners (exclude system accounts)
    owners = db.query(models.User).filter(
        models.User.username.not_in(["Free Agent", "Obsolete", "free agent"])
    ).all()
    
    if not owners:
        print("❌ No owners found! Create users first.")
        return

    # Fetch players by position
    all_qbs = db.query(models.Player).filter(models.Player.position == 'QB').all()
    all_rbs = db.query(models.Player).filter(models.Player.position == 'RB').all()
    all_wrs = db.query(models.Player).filter(models.Player.position == 'WR').all()
    all_tes = db.query(models.Player).filter(models.Player.position == 'TE').all()
    all_ks  = db.query(models.Player).filter(models.Player.position == 'K').all()
    all_defs = db.query(models.Player).filter(models.Player.position == 'DEF').all()

    # Shuffle lists to randomize who gets whom
    for lst in [all_qbs, all_rbs, all_wrs, all_tes, all_ks, all_defs]:
        random.shuffle(lst)

    # Track used IDs to avoid duplicates
    used_player_ids = set()

    # --- C. DRAFT LOGIC ---
    print(f"   - Drafting for {len(owners)} teams...")
    
    for owner in owners:
        roster = []

        # 1. STARTERS (1 QB, 2 RB, 2 WR, 1 TE, 1 K, 1 DEF)
        # We assign them status="STARTER" immediately
        starters = []
        starters.append(all_qbs.pop(0))
        starters.append(all_rbs.pop(0)); starters.append(all_rbs.pop(0))
        starters.append(all_wrs.pop(0)); starters.append(all_wrs.pop(0))
        starters.append(all_tes.pop(0))
        starters.append(all_ks.pop(0))
        starters.append(all_defs.pop(0))

        # 2. BENCH (6 Players)
        bench = []
        for _ in range(2): bench.append(all_rbs.pop(0))
        for _ in range(3): bench.append(all_wrs.pop(0))
        for _ in range(1): bench.append(all_tes.pop(0))

        # 3. COMMIT PICKS TO DB
        # Add Starters
        for player in starters:
            pick = models.DraftPick(
                year=2026,
                session_id="SIMULATED_DRAFT",
                round_num=0,
                pick_num=0,
                amount=random.randint(10, 50),
                current_status="STARTER", # <--- NEW: Set as Starter
                owner_id=owner.id,
                player_id=player.id
            )
            db.add(pick)

        # Add Bench
        for player in bench:
            pick = models.DraftPick(
                year=2026,
                session_id="SIMULATED_DRAFT",
                round_num=0,
                pick_num=0,
                amount=random.randint(1, 10),
                current_status="BENCH", # <--- NEW: Set as Bench
                owner_id=owner.id,
                player_id=player.id
            )
            db.add(pick)

    # --- D. SAVE ---
    db.commit()
    print(f"✅ DRAFT COMPLETE! {len(owners) * 14} picks generated.")
    print(f"   - League is ready for 'Finalize Draft' action.")

if __name__ == "__main__":
    seed_draft()