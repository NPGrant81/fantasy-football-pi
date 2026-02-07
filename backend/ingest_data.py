import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import SessionLocal, engine
# NEW: Added 'League' to the imports
from models import Player, User, DraftPick, Budget, Base, League
import os

# --- SECURITY TOOL ---
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------
# ⚠️ HARD RESET: WIPE & REBUILD DATABASE
# ---------------------------------------------------------
print("⚠️  Wiping Database (Hard Reset)...")
Base.metadata.drop_all(bind=engine) 

print("✅  Rebuilding Tables...")
Base.metadata.create_all(bind=engine) 
# ---------------------------------------------------------

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

def safe_int(val):
    """Safely converts 47.0 or '47' to 47. Returns None if empty/NaN."""
    if pd.isna(val) or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None

def read_csv_safe(path):
    try:
        return pd.read_csv(path, encoding='utf-8')
    except UnicodeDecodeError:
        print(f"⚠️ UTF-8 failed for {os.path.basename(path)}, switching to ISO-8859-1...")
        return pd.read_csv(path, encoding='ISO-8859-1')

def load_lookups():
    pos_map = {}
    path = get_file_path("positions.csv")
    if path:
        df = read_csv_safe(path)
        for _, row in df.iterrows():
            if pd.isna(row['PositionID']): continue
            try:
                pid = str(int(float(row['PositionID'])))
                pos_map[pid] = row['Position']
            except: continue
    
    team_map = {}
    path = get_file_path("teams.csv")
    if path:
        df = read_csv_safe(path)
        for _, row in df.iterrows():
            if pd.isna(row['TeamID']): continue
            try:
                tid = str(int(float(row['TeamID'])))
                team_map[tid] = row['Team']
            except: continue
            
    return pos_map, team_map

def run_ingest():
    db: Session = SessionLocal()
    pos_map, team_map = load_lookups()
    
    default_hash = pwd_context.hash("password123") 
    
    try:
        # ==========================================
        # 0. NEW: CREATE THE LEAGUE
        # ==========================================
        print("🏆 Creating Default League: 'The League'...")
        default_league = League(name="The League")
        db.add(default_league)
        db.commit()
        db.refresh(default_league)
        league_id = default_league.id # We will assign all users to this ID

        # ==========================================
        # 1. USERS (OWNERS)
        # ==========================================
        path = get_file_path("users.csv")
        if path:
            df = read_csv_safe(path)
            # Safe logic to sort users (optional but keeps your old logic)
            if 'OwnerName' in df.columns:
                df['NameLen'] = df['OwnerName'].astype(str).str.len()
                df = df.sort_values('NameLen', ascending=False).drop_duplicates(subset=['OwnerID'])
            
            count = 0
            for _, row in df.iterrows():
                uid = safe_int(row['OwnerID'])
                if not uid: continue
                
                uname = str(row['OwnerName']).strip()
                
                # Check if exists (Redundant after wipe, but good safety)
                existing = db.query(User).filter(User.id == uid).first()
                if not existing:
                    email_slug = "".join(e for e in uname if e.isalnum())
                    
                    db.add(User(
                        id=uid, 
                        username=uname, 
                        email=f"{email_slug}@example.com",
                        hashed_password=default_hash,
                        league_id=league_id  # <--- NEW: Link User to League
                    ))
                    count += 1
            
            db.commit()
            
            # Reset ID sequence for Postgres
            try:
                db.execute(text("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));"))
            except Exception:
                pass

            print(f"✅ Users processed: Added {count} new (Assigned to League ID {league_id}).")

        # ==========================================
        # 2. PLAYERS (Logic Preserved)
        # ==========================================
        latest_teams = {}
        draft_path = get_file_path("draft_results.csv")
        
        if draft_path:
            d_df = read_csv_safe(draft_path)
            d_df = d_df.sort_values('Year', ascending=True)
            for _, row in d_df.iterrows():
                pid = safe_int(row['PlayerID'])
                tid = safe_int(row['TeamID'])
                if pid and tid: 
                    t_str = str(tid)
                    if t_str in team_map:
                        latest_teams[str(pid)] = team_map[t_str]

        path = get_file_path("players.csv")
        if path:
            df = read_csv_safe(path)
            df = df.drop_duplicates(subset=['Player_ID'])
            
            count = 0
            for _, row in df.iterrows():
                pid = safe_int(row['Player_ID'])
                if not pid: continue

                name = str(row['PlayerName']).strip()
                pos_id = safe_int(row['PositionID'])
                pos_str = pos_map.get(str(pos_id), "UNK") if pos_id else "UNK"
                nfl_team_str = latest_teams.get(str(pid), "FA")

                new_p = Player(id=pid, name=name, position=pos_str, nfl_team=nfl_team_str)
                db.add(new_p)
                count += 1
            
            db.commit()
            try:
                db.execute(text("SELECT setval('players_id_seq', (SELECT MAX(id) FROM players));"))
            except Exception:
                pass
            print(f"✅ Players processed: Added {count} new.")

        # ==========================================
        # 3. DRAFT RESULTS & BUDGETS (Logic Preserved)
        # ==========================================
        if draft_path:
            df = read_csv_safe(draft_path)
            count = 0
            for _, row in df.iterrows():
                pid = safe_int(row['PlayerID'])
                oid = safe_int(row['OwnerID'])
                year = safe_int(row['Year'])
                
                if not pid or not oid: continue

                new_pick = DraftPick(
                    player_id = pid,
                    owner_id = oid,
                    year = year if year else 0,
                    amount = clean_money(row['WinningBid']),
                    session_id=f"HISTORICAL_{year}" # Tagging historical data
                )
                db.add(new_pick)
                count += 1
            db.commit()
            print(f"✅ Draft History processed: {count} picks loaded.")

        path = get_file_path("draft_budget.csv")
        if path:
            df = read_csv_safe(path)
            for _, row in df.iterrows():
                oid = safe_int(row['OwnerID'])
                if not oid: continue
                year_raw = str(row['Year'])
                if '/' in year_raw:
                    try: year = int(year_raw.split('/')[-1])
                    except: year = 2024
                else:
                    year = safe_int(year_raw) or 2024

                new_budget = Budget(
                    owner_id = oid,
                    year = year,
                    total_budget = clean_money(row['DraftBudget'])
                )
                db.add(new_budget)
            db.commit()
            print("✅ Budgets processed.")

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run_ingest()