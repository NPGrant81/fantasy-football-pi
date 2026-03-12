import nfl_data_py as nfl
import pandas as pd
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
try:
    # Support both module execution (python -m backend.scripts.import_nfl_data)
    # and direct script execution from backend/scripts.
    from backend.services import player_service
except ModuleNotFoundError:
    from services import player_service

# 1. Initialize DB
models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

def import_fresh_data():
    print("🏈 Fetching LIVE NFL Data (2025 Season)...")
    
    # --- A. FETCH PLAYERS ---
    try:
        df = nfl.import_seasonal_rosters([2025])
    except Exception as e:
        print(f"❌ Error fetching NFL data: {e}")
        return

    # --- B. FILTER & NORMALIZE ---
    print(f"   - Raw pool: {len(df)} players")
    
    # 1. Standardize Positions
    df['position'] = df['position'].replace({'FB': 'RB'})
    
    # 2. Filter for Fantasy Positions
    fantasy_positions = ['QB', 'RB', 'WR', 'TE', 'K']
    active_players = df[df['position'].isin(fantasy_positions)].copy()
    
    # 3. Clean Names & Teams
    active_players = active_players.dropna(subset=['team'])
    active_players = active_players.dropna(subset=['player_name'])

    seen_player_keys = set()
    deduped_rows = []
    for _, row in active_players.iterrows():
        name = row['player_name']
        position = row['position']
        team = row['team']
        if not player_service.is_valid_fantasy_player(
            name=name,
            position=position,
            nfl_team=team,
        ):
            continue
        key = player_service.canonical_player_identity(name, position, team)
        if key in seen_player_keys:
            continue
        seen_player_keys.add(key)
        deduped_rows.append(row)

    active_players = pd.DataFrame(deduped_rows)
    
    print(f"   - Fantasy Eligible: {len(active_players)} players (QB/RB/WR/TE/K)")

    # --- C. WIPE OLD DATA (Order Matters!) ---
    print("🗑️  Cleaning Database...")
    try:
        # 1. Delete Draft Picks first (Foreign Key Dependency)
        print("   - Clearing Draft Picks...")
        db.query(models.DraftPick).delete()
        
        # 2. Delete Players second
        print("   - Clearing Players...")
        db.query(models.Player).delete()
        
        db.commit()
    except Exception as e:
        print(f"   - Error clearing tables: {e}")
        db.rollback()
        return

    # --- D. INSERT INDIVIDUAL PLAYERS ---
    print("💾 Saving new players to database...")
    count = 0
    for _, row in active_players.iterrows():
        player = models.Player(
            name=row['player_name'],
            position=row['position'],
            nfl_team=row['team'],
            gsis_id=str(row['player_id']), # Ensure string
            bye_week=None 
        )
        db.add(player)
        count += 1
    
    # --- E. GENERATE TEAM DEFENSES ---
    print("🛡️  Generating 32 Team Defenses...")
    nfl_teams = active_players['team'].unique()
    
    for team_abbr in nfl_teams:
        defense = models.Player(
            name=f"{team_abbr} Defense",
            position="DEF",
            nfl_team=team_abbr,
            gsis_id=f"DEF_{team_abbr}",
            bye_week=None
        )
        db.add(defense)
        count += 1

    db.commit()
    print(f"✅ Success! Imported {count} total draftable assets.")

if __name__ == "__main__":
    import_fresh_data()