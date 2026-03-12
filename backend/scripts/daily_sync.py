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
try:
    # Support both module execution (python -m backend.scripts.daily_sync)
    # and direct script execution from backend/scripts.
    from backend.services import player_service
except ModuleNotFoundError:
    from services import player_service

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
        name = row.get('display_name') or row.get('player_name') or row.get('first_name')
        position = row.get('position')
        team = row.get('team')
        if not player_service.is_valid_fantasy_player(
            name=name,
            position=position,
            nfl_team=team,
        ):
            continue

        player = player_service.find_existing_player(
            db,
            gsis_id=str(row['gsis_id']) if row.get('gsis_id') else None,
            name=name,
            position=position,
            nfl_team=team,
        )
        if player:
            player.gsis_id = str(row['gsis_id']) if row.get('gsis_id') else player.gsis_id
            # Update their team if they've been traded or moved
            if player.nfl_team != team:
                print(f"🚀 Trade Alert: {player.name} moved from {player.nfl_team} to {team}")
                player.nfl_team = team
    
    db.commit()
    print("✨ NFL Reality Sync Complete.")

if __name__ == "__main__":
    sync_nfl_reality()

# end of file - trigger a new push for CI
