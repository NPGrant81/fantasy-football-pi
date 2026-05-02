import sys
import os
import pandas as pd

# Add the parent directory (backend) to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# backend/scripts/daily_sync.py
# Uses direct ESPN roster APIs via backend.services.espn_roster_service.
from database import SessionLocal
import models
try:
    # Support both module execution (python -m backend.scripts.daily_sync)
    # and direct script execution from backend/scripts.
    from backend.services import player_service
except ModuleNotFoundError:
    from services import player_service
try:
    from backend.services.player_identity_service import (
        current_season,
        deactivate_stale_player_seasons,
        upsert_player_season,
    )
    from backend.services.nfl_roster_provider_service import fetch_current_players
except ModuleNotFoundError:
    from services.player_identity_service import (
        current_season,
        deactivate_stale_player_seasons,
        upsert_player_season,
    )
    from services.nfl_roster_provider_service import fetch_current_players

def sync_nfl_reality():
    db = SessionLocal()
    print("🔄 Pulling latest NFL roster data from ESPN...")
    
    df = fetch_current_players()
    if df.empty:
        print("⚠️ ESPN roster fetch returned no rows; skipping reality sync")
        db.close()
        return
    
    # Filter for active players to keep it fast
    active_players = df[df['status'] == 'Active']
    
    season = current_season()
    # Collect the set of local player IDs confirmed active in this feed run.
    # Used after the loop to deactivate players absent from the current roster.
    seen_player_ids: set[int] = set()

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

        raw_espn_id = row.get('player_id')
        if pd.isna(raw_espn_id):
            espn_id = None
        else:
            espn_id = str(raw_espn_id).strip()
            if espn_id.lower() in {'', 'nan', 'none', 'null'}:
                espn_id = None

        player = player_service.find_existing_player(
            db,
            gsis_id=None,
            espn_id=espn_id,
            name=name,
            position=position,
            nfl_team=team,
        )
        if player:
            # Update ESPN ID if we have it and it's missing from the record
            if espn_id and not player.espn_id:
                player.espn_id = espn_id
            # Update their team if they've been traded or moved
            if player.nfl_team != team:
                print(f"🚀 Trade Alert: {player.name} moved from {player.nfl_team} to {team}")
                player.nfl_team = team
            upsert_player_season(
                db,
                player_id=int(player.id),
                season=season,
                nfl_team=team,
                position=player.position,
                bye_week=player.bye_week,
                is_active=True,
                source="nfl_daily_sync",
            )
            seen_player_ids.add(int(player.id))

    # --- Deactivation pass ---
    # Any player with an active PlayerSeason this year who did NOT appear in
    # today's feed is presumed retired/cut/IR.  DEF rows are excluded.
    # The threshold guard (100) prevents mass-deactivation from a bad fetch.
    deactivated = deactivate_stale_player_seasons(
        db,
        season=season,
        active_player_ids=seen_player_ids,
    )
    if deactivated:
        print(f"🚫 Marked {deactivated} player-season(s) inactive (absent from feed)")

    db.commit()
    print("✨ NFL Reality Sync Complete.")

if __name__ == "__main__":
    sync_nfl_reality()

# end of file - trigger a new push for CI
