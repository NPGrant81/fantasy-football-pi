import sys
import os

# Add the parent directory (backend) to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# backend/scripts/daily_sync.py
# nfl_data_py is an optional dependency used by the reality sync.
# import lazily inside the function so that tests that import `main` will not
# fail if the package isn't installed.
from database import SessionLocal
import models

def sync_nfl_reality():
    # import here to avoid requiring the package in lightweight test runs
    try:
        # optional; may not be installed in minimal environments
        import nfl_data_py as nfl  # type: ignore[import]
    except ImportError:
        print("⚠️ nfl_data_py not installed; skipping reality sync")
        return

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

# end of file - trigger a new push for CI
