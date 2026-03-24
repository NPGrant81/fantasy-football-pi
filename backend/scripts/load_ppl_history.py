"""
One-time script: loads historical draft data into Postgres scoped to Post Pacific League.
Safe to run multiple times (idempotent checks included).
"""
import os, sys
from pathlib import Path
import pandas as pd
import psycopg2


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.db_config import load_backend_env_file, resolve_database_url

# --- Config ---
LEAGUE_ID = 60  # Post Pacific League
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BCRYPT_PLACEHOLDER = "$2b$12$AT98P1yMsFB6voQYGgVxEO21tf6tZuXl79b/j615NkIKMhnx0LL3W"


load_backend_env_file()
DB_URL = resolve_database_url(require_explicit=True, context="backend/scripts/load_ppl_history.py")


def connect():
    return psycopg2.connect(DB_URL)


def clean_money(val):
    try:
        if val != val:
            return 0.0
        return float(str(val).replace("$", "").replace(",", "").strip())
    except Exception:
        return 0.0


def safe_int(val):
    try:
        if val != val:
            return None
        return int(float(val))
    except Exception:
        return None


def load_positions(data_dir):
    path = os.path.join(data_dir, "positions.csv")
    df = pd.read_csv(path)
    return {str(int(float(r["PositionID"]))): r["Position"] for _, r in df.iterrows() if not pd.isna(r["PositionID"])}


def load_canonical_owners(data_dir):
    path = os.path.join(data_dir, "users.csv")
    df = pd.read_csv(path, encoding="ISO-8859-1")
    return df.drop_duplicates(subset=["OwnerID"], keep="first").copy()


def build_owner_email(owner_name):
    slug = "".join(ch.lower() if ch.isalnum() else "." for ch in owner_name.strip())
    slug = ".".join(part for part in slug.split(".") if part)
    return f"{slug}@postpacific.local"


def step1_sync_owners(cur, owner_df):
    synced = 0
    inserted = 0

    for _, row in owner_df.iterrows():
        owner_id = safe_int(row["OwnerID"])
        owner_name = str(row["OwnerName"]).strip()
        if not owner_id or not owner_name:
            continue

        email = build_owner_email(owner_name)
        is_nick = owner_id == 1

        cur.execute("SELECT id FROM public.users WHERE id = %s", (owner_id,))
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """
                UPDATE public.users
                SET
                    username = %s,
                    email = %s,
                    league_id = %s,
                    is_superuser = %s,
                    is_commissioner = %s,
                    team_name = %s
                WHERE id = %s
                """,
                (owner_name, email, LEAGUE_ID, is_nick, is_nick, owner_name, owner_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO public.users (
                    id,
                    username,
                    email,
                    hashed_password,
                    is_superuser,
                    is_commissioner,
                    league_id,
                    team_name
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (owner_id, owner_name, email, BCRYPT_PLACEHOLDER, is_nick, is_nick, LEAGUE_ID, owner_name),
            )
            inserted += 1

        synced += 1

    cur.execute("DELETE FROM public.users WHERE id = 85")
    print(f"  Owners synced: {synced} (inserted {inserted}).")


def step2_load_players(cur, data_dir, pos_map):
    path = os.path.join(data_dir, "players.csv")
    df = pd.read_csv(path, encoding="ISO-8859-1").drop_duplicates(subset=["Player_ID"])

    cur.execute("SELECT id FROM public.players")
    existing = set(r[0] for r in cur.fetchall())
    print(f"  Players already in DB: {len(existing)}")

    inserted = 0
    for _, row in df.iterrows():
        pid = safe_int(row["Player_ID"])
        if not pid or pid in existing:
            continue
        name = str(row["PlayerName"]).strip()
        pos_id_str = str(safe_int(row.get("PositionID"))) if safe_int(row.get("PositionID")) else None
        pos = pos_map.get(pos_id_str, "UNK")
        cur.execute(
            "INSERT INTO public.players (id, name, position, nfl_team) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (pid, name, pos, "FA"),
        )
        inserted += 1

    print(f"  Players inserted: {inserted}")


def step3_load_draft_picks(cur, data_dir):
    cur.execute(
        "SELECT COUNT(*) FROM public.draft_picks WHERE league_id = %s AND session_id LIKE 'HISTORICAL_%%'",
        (LEAGUE_ID,),
    )
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"  Historical picks already loaded for league_id={LEAGUE_ID} ({existing} rows) — skip.")
        return

    path = os.path.join(data_dir, "draft_results.csv")
    df = pd.read_csv(path)
    print(f"  Draft CSV rows: {len(df)}")

    inserted = 0
    skipped = 0
    for _, row in df.iterrows():
        pid = safe_int(row["PlayerID"])
        oid = safe_int(row["OwnerID"])
        year = safe_int(row["Year"])
        if not pid or not oid:
            skipped += 1
            continue
        cur.execute(
            """
            INSERT INTO public.draft_picks (player_id, owner_id, year, amount, session_id, league_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (pid, oid, year or 0, clean_money(row["WinningBid"]), f"HISTORICAL_{year}", LEAGUE_ID),
        )
        inserted += 1

    print(f"  Draft picks inserted: {inserted} (skipped {skipped})")


def main():
    conn = connect()
    cur = conn.cursor()
    try:
        pos_map = load_positions(DATA_DIR)
        owner_df = load_canonical_owners(DATA_DIR)

        print("Step 1: Syncing canonical Post Pacific owners...")
        step1_sync_owners(cur, owner_df)
        conn.commit()

        print("Step 2: Loading missing players...")
        step2_load_players(cur, DATA_DIR, pos_map)
        conn.commit()

        print("Step 3: Loading historical draft picks...")
        step3_load_draft_picks(cur, DATA_DIR)
        conn.commit()

        print("\nDone.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
