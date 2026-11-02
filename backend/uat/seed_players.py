# backend/uat/seed_players.py
import requests
from sqlalchemy.orm import Session
from backend import models
from backend.services.player_service import find_existing_player

def seed_players(db: Session):
    print("🌐 FETCHING PLAYERS: Connecting to Sleeper API...")

    # 1.1 DATA: Fetch the master player list
    # Note: This is a large file (~5MB), but Sleeper is fast.
    url = "https://api.sleeper.app/v1/players/nfl"
    response = requests.get(url, timeout=30)
    
    response.raise_for_status()

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
            exists = find_existing_player(
                db, sleeper_id=str(p_id), gsis_id=data.get("gsis_id"),
                name=data.get("full_name") or data.get("last_name"),
                position=data.get("position"), nfl_team=data.get("team") or "FA",
            )
            
            if not exists:
                new_player = models.Player(
                    name=data.get("full_name") or data.get("last_name"),
                    position=data.get("position"),
                    nfl_team=data.get("team") or "FA",
                    sleeper_id=str(p_id),
                    gsis_id=data.get("gsis_id") or None,
                    projected_points=0.0 # Projections require a separate call/logic
                )
                db.add(new_player)
                count += 1
            else:
                exists.sleeper_id = str(p_id)
                if data.get("gsis_id"):
                    exists.gsis_id = data["gsis_id"]
            db.flush()
                
        # To avoid a massive first-time seed, let's cap it at 300 players for UAT
        if count >= 300:
            break
            
    db.commit()
    print(f"✅ Seeding Complete: {count} NFL players added to the pool.")