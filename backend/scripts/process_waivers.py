# backend/scripts/process_waivers.py
from database import SessionLocal
import models

def run_waiver_cycle(league_id):
    db = SessionLocal()
    # 1. Get all pending claims for this week, sorted by creation time
    claims = db.query(models.WaiverClaim).filter(models.WaiverClaim.league_id == league_id).all()
    
    # 2. Get Waiver Priority (Inverse of standings)
    # This ensures the "fastest clicker" doesn't win, but the most needy team does
    priority_list = db.query(models.User).filter(models.User.league_id == league_id).order_by(models.User.wins.asc()).all()
    
    for owner in priority_list:
        # Find this owner's highest-ranked claim that is still available
        owner_claims = [c for c in claims if c.owner_id == owner.id]
        for claim in owner_claims:
            # Logic: If player still a free agent, swap them and move owner to end of priority
            print(f"Processing claim for {owner.username}: Adding Player {claim.player_id}")
            break 

    db.commit()
