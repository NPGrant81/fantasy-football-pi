import nfl_data_py as nfl
import pandas as pd
from sqlalchemy.orm import Session
from database import SessionLocal
import models

def run_update():
    # 1. Connect to Database
    db = SessionLocal()
    print("🏈 Fetching latest NFL rosters from the cloud...")

    # 2. Fetch Data (2024 and 2025)
    # Returns columns: 'player_name', 'position', 'team', 'status', 'player_id' (gsis_id), 'season'
    try:
        df = nfl.import_seasonal_rosters([2024, 2025])
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return

    print(f"📥 Downloaded {len(df)} rows.")

    # --- THE FIX: DEDUPLICATE DATA ---
    # Sort by season (ascending) so the latest season is last
    df = df.sort_values(by=['season'], ascending=True)
    # Drop duplicates based on 'player_id', keeping the LAST (latest) entry
    df = df.drop_duplicates(subset=['player_id'], keep='last')
    
    print(f"✅ Processing {len(df)} unique players...")
    # ---------------------------------

    updates = 0
    new_additions = 0
    
    # We use a local cache of IDs currently in the DB to speed things up
    # and ensure we don't hit the DB for every single row.
    existing_gsis_ids = {x[0] for x in db.query(models.Player.gsis_id).filter(models.Player.gsis_id != None).all()}
    existing_names = {x[0]: x[1] for x in db.query(models.Player.name, models.Player).all()}

    for index, row in df.iterrows():
        p_name = row['player_name']
        p_id = row['player_id'] # The official NFL ID
        p_team = row['team']
        p_pos = row['position']
        
        if not p_name or not p_id: 
            continue

        # SCENARIO A: Player exists by GSIS ID (The Perfect Match)
        if p_id in existing_gsis_ids:
            # We could fetch the object to update team, but for speed we skip if known.
            # To strictly update teams, we would need to fetch the object.
            # Let's do a quick query only if we want to ensure latest team:
            player = db.query(models.Player).filter(models.Player.gsis_id == p_id).first()
            if player and player.nfl_team != p_team:
                player.nfl_team = p_team
                updates += 1
            continue

        # SCENARIO B: Player exists by Name but missing GSIS ID (The Link-Up)
        elif p_name in existing_names:
            player = existing_names[p_name]
            # Link them forever now
            player.gsis_id = p_id 
            player.nfl_team = p_team
            player.position = p_pos
            existing_gsis_ids.add(p_id) # Add to local cache so we don't re-add
            updates += 1

        # SCENARIO C: Totally New Player
        else:
            new_player = models.Player(
                name=p_name,
                position=p_pos,
                nfl_team=p_team,
                gsis_id=p_id
            )
            db.add(new_player)
            existing_gsis_ids.add(p_id) # Add to cache
            existing_names[p_name] = new_player # Add to cache
            new_additions += 1

    db.commit()
    db.close()

    print("------------------------------------------------")
    print(f"🏆 Roster Sync Complete!")
    print(f"   - Updated/Linked Players: {updates}")
    print(f"   - New Players Added: {new_additions}")
    print("------------------------------------------------")

if __name__ == "__main__":
    run_update()