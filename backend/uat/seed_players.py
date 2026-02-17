# backend/uat/seed_players.py
import requests
from sqlalchemy.orm import Session
import models

def seed_players(db: Session):
    print("🌐 FETCHING PLAYERS: Connecting to Sleeper API...")

    # 1.1 DATA: Fetch the master player list
    # Note: This is a large file (~5MB), but Sleeper is fast.
    url = "https://api.sleeper.app/v1/players/nfl"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"❌ Error: Sleeper API returned {response.status_code}")
        return

    raw_players = response.json()
    
    # 1.2 FILTERING: We only want active players in fantasy positions
    # Valid positions for our league: QB, RB, WR, TE, K, DEF
    valid_pos = {"QB", "RB", "WR", "TE", "K", "DEF"}
    
    # 2.1 EXECUTION: Map and Seed
    print("🌱 Processing and Seeding Players...")
    count = 0
    
    for p_id, data in raw_players.items():
        # Filtering for active players in our target positions
        if data.get("active") and data.get("position") in valid_pos:
            # Avoid duplicates using the 'gsis_id' column
            # We use Sleeper's internal ID as our unique key for UAT
            exists = db.query(models.Player).filter(models.Player.gsis_id == p_id).first()
            
            if not exists:
                new_player = models.Player(
                    name=data.get("full_name") or data.get("last_name"),
                    position=data.get("position"),
                    nfl_team=data.get("team") or "FA",
                    gsis_id=p_id, # This is the unique Sleeper ID
                    projected_points=0.0 # Projections require a separate call/logic
                )
                db.add(new_player)
                count += 1
                
        # To avoid a massive first-time seed, let's cap it at 300 players for UAT
        if count >= 300:
            break
            
    db.commit()
    print(f"✅ Seeding Complete: {count} NFL players added to the pool.")