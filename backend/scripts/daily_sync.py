# backend/scripts/daily_sync.py
import nfl_data_py as nfl
from database import SessionLocal
import models

def sync_nfl_reality():
    db = SessionLocal()
    print("🔄 Pulling latest NFL roster data...")
    
    # Fetch latest player data for 2025/2026
    df = nfl.import_players()
    
    # Filter for active players to keep it fast
    active_players = df[df['status'] == 'Active']
    
    for _, row in active_players.iterrows():
        player = db.query(models.Player).filter(models.Player.gsis_id == row['gsis_id']).first()
        if player:
            # Update their team if they've been traded or moved
            if player.nfl_team != row['team']:
                print(f"🚀 Trade Alert: {player.name} moved from {player.nfl_team} to {row['team']}")
                player.nfl_team = row['team']
    
    db.commit()
    print("✨ NFL Reality Sync Complete.")

if __name__ == "__main__":
    sync_nfl_reality()
