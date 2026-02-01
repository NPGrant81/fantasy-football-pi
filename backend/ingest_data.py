import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import SessionLocal, engine
from models import Player, User, DraftPick, Budget, Base
import os

# 1. Initialize DB
Base.metadata.create_all(bind=engine)

def get_file_path(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.exists(path):
        print(f"⚠️ Warning: '{filename}' not found. Skipping.")
        return None
    return path

def clean_money(val):
    """Converts '$47.00 ' to 47.0"""
    if not val or pd.isna(val): return 0.0
    return float(str(val).replace('$', '').replace(',', '').strip())

# ---------------------------------------------------------
# LOAD LOOKUP MAPS (Teams & Positions)
# ---------------------------------------------------------
def load_lookups():
    # 1. Map Position IDs (8002 -> QB)
    pos_map = {}
    path = get_file_path("positions.csv")
    if path:
        df = pd.read_csv(path)
        # Handle both string/int inputs
        for _, row in df.iterrows():
            pid = str(row['PositionID']).split('.')[0] # Remove .0 if present
            pos_map[pid] = row['Position']
    
    # 2. Map Team IDs (9001 -> ARI)
    team_map = {}
    path = get_file_path("teams.csv")
    if path:
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            tid = str(row['TeamID']).split('.')[0]
            team_map[tid] = row['Team']
            
    print(f"✅ Loaded Mappings: {len(pos_map)} positions, {len(team_map)} teams.")
    return pos_map, team_map

# ---------------------------------------------------------
# MAIN INGEST FUNCTION
# ---------------------------------------------------------
def run_ingest():
    db: Session = SessionLocal()
    pos_map, team_map = load_lookups()
    
    try:
        # ==========================================
        # 1. USERS (OWNERS)
        # ==========================================
        path = get_file_path("users.csv")
        if path:
            df = pd.read_csv(path)
            # Deduplicate: Group by OwnerID and pick the longest name (Nick Grant > NPG)
            # This handles the "1, Nick Grant" vs "1, NPG" issue
            df['NameLen'] = df['OwnerName'].astype(str).str.len()
            df = df.sort_values('NameLen', ascending=False).drop_duplicates(subset=['OwnerID'])
            
            count = 0
            for _, row in df.iterrows():
                uid = int(row['OwnerID'])
                uname = row['OwnerName'].strip()
                
                existing = db.query(User).filter(User.id == uid).first()
                if not existing:
                    db.add(User(id=uid, username=uname, email=f"{uname.replace(' ','')}@example.com"))
                    count += 1
                else:
                    existing.username = uname # Update name if changed
            
            db.commit()
            # Fix Postgres ID Sequence
            db.execute(text("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));"))
            print(f"✅ Users processed: Added {count} new.")

        # ==========================================
        # 2. PLAYERS
        # ==========================================
        # Strategy: Use draft_results to find the Player's NFL Team if possible
        latest_teams = {}
        draft_path = get_file_path("draft_results.csv")
        if draft_path:
            d_df = pd.read_csv(draft_path)
            d_df = d_df.sort_values('Year', ascending=True) # Oldest to Newest
            for _, row in d_df.iterrows():
                pid = str(int(row['PlayerID']))
                tid = str(int(row['TeamID']))
                if tid in team_map:
                    latest_teams[pid] = team_map[tid]

        path = get_file_path("players.csv")
        if path:
            df = pd.read_csv(path)
            # Deduplicate Players by ID (keep first valid one)
            df = df.drop_duplicates(subset=['Player_ID'])
            
            count = 0
            for _, row in df.iterrows():
                pid = int(row['Player_ID'])
                name = row['PlayerName'].strip()
                
                # Map Position ID to String (8004 -> WR)
                pos_id = str(int(row['PositionID']))
                pos_str = pos_map.get(pos_id, "UNK")
                
                # Determine NFL Team
                # First check our lookup from draft history, default to FA
                nfl_team_str = latest_teams.get(str(pid), "FA")

                existing = db.query(Player).filter(Player.id == pid).first()
                if not existing:
                    new_p = Player(id=pid, name=name, position=pos_str, nfl_team=nfl_team_str)
                    db.add(new_p)
                    count += 1
                else:
                    # Update existing info
                    existing.nfl_team = nfl_team_str
                    existing.position = pos_str
            
            db.commit()
            db.execute(text("SELECT setval('players_id_seq', (SELECT MAX(id) FROM players));"))
            print(f"✅ Players processed: Added {count} new.")

        # ==========================================
        # 3. DRAFT RESULTS (History)
        # ==========================================
        if draft_path:
            df = pd.read_csv(draft_path)
            count = 0
            # Clear old draft picks to avoid duplicates on re-run (Optional)
            db.query(DraftPick).delete()
            
            for _, row in df.iterrows():
                new_pick = DraftPick(
                    player_id = int(row['PlayerID']),
                    owner_id = int(row['OwnerID']),
                    year = int(row['Year']),
                    amount = clean_money(row['WinningBid'])
                )
                db.add(new_pick)
                count += 1
            db.commit()
            print(f"✅ Draft History processed: {count} picks loaded.")

        # ==========================================
        # 4. BUDGETS
        # ==========================================
        path = get_file_path("draft_budget.csv")
        if path:
            df = pd.read_csv(path)
            db.query(Budget).delete() # Refresh budgets
            
            for _, row in df.iterrows():
                # Extract year from '1/1/2024' -> 2024
                year_str = str(row['Year'])
                if '/' in year_str:
                    year = int(year_str.split('/')[-1])
                else:
                    year = int(year_str)

                new_budget = Budget(
                    owner_id = int(row['OwnerID']),
                    year = year,
                    total_budget = clean_money(row['DraftBudget'])
                )
                db.add(new_budget)
            db.commit()
            print(f"✅ Budgets processed.")

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run_ingest()