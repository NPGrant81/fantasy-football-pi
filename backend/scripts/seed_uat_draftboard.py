"""Seed a full UAT draft board for The Big Show (league 1).

Creates:
  - 10 fantasy team owners (UAT_Owner_01 … UAT_Owner_10) in league 1
  - 50 NFL players across all fantasy-relevant positions
  - DraftValue rows for 2026 so /draft/rankings returns data
  - DraftPick history for 2023-2025 (3 seasons) so historical rankings work
  - Some players with injury designations and projected return dates

Usage (from repo root):
    python -m backend.scripts.seed_uat_draftboard [--league-id 1] [--season 2026] [--reset]

Pass --reset to wipe existing UAT owners / players before reseeding.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

REPO_ROOT_HINT = "Run from the repo root: python -m backend.scripts.seed_uat_draftboard"

# ---------------------------------------------------------------------------
# UAT DATA
# ---------------------------------------------------------------------------

_OWNERS: list[dict] = [
    {"username": "uat_owner_01", "team_name": "Steel City Grinders",    "email": "uat01@uat.local"},
    {"username": "uat_owner_02", "team_name": "Bayou Brawlers",         "email": "uat02@uat.local"},
    {"username": "uat_owner_03", "team_name": "Desert Storm",           "email": "uat03@uat.local"},
    {"username": "uat_owner_04", "team_name": "Pacific Rim Renegades",  "email": "uat04@uat.local"},
    {"username": "uat_owner_05", "team_name": "Mountain Men",           "email": "uat05@uat.local"},
    {"username": "uat_owner_06", "team_name": "Gulf Coast Gators",      "email": "uat06@uat.local"},
    {"username": "uat_owner_07", "team_name": "Heartland Hammers",      "email": "uat07@uat.local"},
    {"username": "uat_owner_08", "team_name": "Northeast Nighthawks",   "email": "uat08@uat.local"},
    {"username": "uat_owner_09", "team_name": "Lone Star Lightning",    "email": "uat09@uat.local"},
    {"username": "uat_owner_10", "team_name": "Great Lakes Grizzlies",  "email": "uat10@uat.local"},
]

# Fields: name, position, nfl_team, adp, projected_points, bye_week, espn_id
#         injury_status, injury_notes, projected_return_date, projected_return_week
_PLAYERS: list[dict] = [
    # ── QBs ─────────────────────────────────────────────────────────────────
    {"name": "Lamar Jackson",     "position": "QB", "nfl_team": "BAL", "adp": 1.5,  "projected_points": 420, "bye_week": 14, "espn_id": "3916387"},
    {"name": "Josh Allen",        "position": "QB", "nfl_team": "BUF", "adp": 2.1,  "projected_points": 410, "bye_week": 12},
    {"name": "Jalen Hurts",       "position": "QB", "nfl_team": "PHI", "adp": 3.0,  "projected_points": 390, "bye_week": 5,
     "injury_status": "QUESTIONABLE", "injury_notes": "Shoulder — limited in practice", "projected_return_week": 1},
    {"name": "CJ Stroud",         "position": "QB", "nfl_team": "HOU", "adp": 6.0,  "projected_points": 350, "bye_week": 10},
    {"name": "Dak Prescott",      "position": "QB", "nfl_team": "DAL", "adp": 7.5,  "projected_points": 330, "bye_week": 7},
    {"name": "Tua Tagovailoa",    "position": "QB", "nfl_team": "MIA", "adp": 9.0,  "projected_points": 315, "bye_week": 6,
     "injury_status": "DOUBTFUL",     "injury_notes": "Concussion protocol — DNP Wednesday"},
    {"name": "Sam Darnold",       "position": "QB", "nfl_team": "MIN", "adp": 12.0, "projected_points": 290, "bye_week": 6},
    {"name": "Brock Purdy",       "position": "QB", "nfl_team": "SF",  "adp": 4.5,  "projected_points": 370, "bye_week": 9},

    # ── RBs ─────────────────────────────────────────────────────────────────
    {"name": "Christian McCaffrey","position": "RB", "nfl_team": "SF",  "adp": 1.0,  "projected_points": 340, "bye_week": 9,
     "injury_status": "OUT",          "injury_notes": "Calf — ruled out this week", "projected_return_date": "2026-09-21", "projected_return_week": 2},
    {"name": "Breece Hall",        "position": "RB", "nfl_team": "NYJ", "adp": 4.2,  "projected_points": 295, "bye_week": 12},
    {"name": "De'Von Achane",      "position": "RB", "nfl_team": "MIA", "adp": 5.0,  "projected_points": 288, "bye_week": 6},
    {"name": "Bijan Robinson",     "position": "RB", "nfl_team": "ATL", "adp": 3.5,  "projected_points": 305, "bye_week": 11},
    {"name": "Jahmyr Gibbs",       "position": "RB", "nfl_team": "DET", "adp": 6.5,  "projected_points": 270, "bye_week": 5},
    {"name": "Josh Jacobs",        "position": "RB", "nfl_team": "GB",  "adp": 9.0,  "projected_points": 245, "bye_week": 5,
     "injury_status": "IR",           "injury_notes": "ACL — season-ending surgery", "projected_return_date": "2027-08-01"},
    {"name": "Tony Pollard",       "position": "RB", "nfl_team": "TEN", "adp": 11.0, "projected_points": 228, "bye_week": 5},
    {"name": "Derrick Henry",      "position": "RB", "nfl_team": "BAL", "adp": 10.5, "projected_points": 235, "bye_week": 14},
    {"name": "Kyren Williams",     "position": "RB", "nfl_team": "LAR", "adp": 8.0,  "projected_points": 255, "bye_week": 7},
    {"name": "Travis Etienne",     "position": "RB", "nfl_team": "JAX", "adp": 13.5, "projected_points": 220, "bye_week": 11},
    {"name": "Aaron Jones",        "position": "RB", "nfl_team": "MIN", "adp": 17.0, "projected_points": 200, "bye_week": 6},
    {"name": "Joe Mixon",          "position": "RB", "nfl_team": "HOU", "adp": 14.0, "projected_points": 215, "bye_week": 10},

    # ── WRs ─────────────────────────────────────────────────────────────────
    {"name": "Ja'Marr Chase",      "position": "WR", "nfl_team": "CIN", "adp": 2.5,  "projected_points": 310, "bye_week": 7},
    {"name": "CeeDee Lamb",        "position": "WR", "nfl_team": "DAL", "adp": 3.0,  "projected_points": 305, "bye_week": 7},
    {"name": "Justin Jefferson",   "position": "WR", "nfl_team": "MIN", "adp": 4.0,  "projected_points": 295, "bye_week": 6},
    {"name": "Tyreek Hill",        "position": "WR", "nfl_team": "MIA", "adp": 5.0,  "projected_points": 285, "bye_week": 6},
    {"name": "A.J. Brown",         "position": "WR", "nfl_team": "PHI", "adp": 6.5,  "projected_points": 270, "bye_week": 5},
    {"name": "Davante Adams",      "position": "WR", "nfl_team": "NYJ", "adp": 8.0,  "projected_points": 250, "bye_week": 12,
     "injury_status": "QUESTIONABLE", "injury_notes": "Hamstring — limited Wednesday"},
    {"name": "Stefon Diggs",       "position": "WR", "nfl_team": "HOU", "adp": 10.5, "projected_points": 230, "bye_week": 10},
    {"name": "Jaylen Waddle",      "position": "WR", "nfl_team": "MIA", "adp": 9.0,  "projected_points": 240, "bye_week": 6},
    {"name": "Amon-Ra St. Brown",  "position": "WR", "nfl_team": "DET", "adp": 7.0,  "projected_points": 260, "bye_week": 5},
    {"name": "Puka Nacua",         "position": "WR", "nfl_team": "LAR", "adp": 12.0, "projected_points": 220, "bye_week": 7},
    {"name": "Mike Evans",         "position": "WR", "nfl_team": "TB",  "adp": 13.0, "projected_points": 215, "bye_week": 11},
    {"name": "Chris Olave",        "position": "WR", "nfl_team": "NO",  "adp": 14.0, "projected_points": 210, "bye_week": 12},
    {"name": "Drake London",       "position": "WR", "nfl_team": "ATL", "adp": 11.0, "projected_points": 225, "bye_week": 11},
    {"name": "Deebo Samuel",       "position": "WR", "nfl_team": "SF",  "adp": 16.0, "projected_points": 195, "bye_week": 9},

    # ── TEs ─────────────────────────────────────────────────────────────────
    {"name": "Travis Kelce",       "position": "TE", "nfl_team": "KC",  "adp": 3.0,  "projected_points": 245, "bye_week": 6},
    {"name": "Sam LaPorta",        "position": "TE", "nfl_team": "DET", "adp": 8.0,  "projected_points": 185, "bye_week": 5},
    {"name": "Trey McBride",       "position": "TE", "nfl_team": "ARI", "adp": 6.0,  "projected_points": 205, "bye_week": 11},
    {"name": "Mark Andrews",       "position": "TE", "nfl_team": "BAL", "adp": 5.5,  "projected_points": 210, "bye_week": 14,
     "injury_status": "DOUBTFUL",     "injury_notes": "Shoulder — did not practice Thursday", "projected_return_week": 2},
    {"name": "Dalton Kincaid",     "position": "TE", "nfl_team": "BUF", "adp": 12.0, "projected_points": 165, "bye_week": 12},
    {"name": "Kyle Pitts",         "position": "TE", "nfl_team": "ATL", "adp": 10.0, "projected_points": 175, "bye_week": 11},
    {"name": "David Njoku",        "position": "TE", "nfl_team": "CLE", "adp": 11.0, "projected_points": 170, "bye_week": 10},
    {"name": "Evan Engram",        "position": "TE", "nfl_team": "JAX", "adp": 9.0,  "projected_points": 180, "bye_week": 11},

    # ── Ks ──────────────────────────────────────────────────────────────────
    {"name": "Justin Tucker",      "position": "K",   "nfl_team": "BAL", "adp": 140, "projected_points": 155, "bye_week": 14},
    {"name": "Evan McPherson",     "position": "K",   "nfl_team": "CIN", "adp": 145, "projected_points": 148, "bye_week": 7},
    {"name": "Brandon McManus",    "position": "K",   "nfl_team": "GB",  "adp": 150, "projected_points": 142, "bye_week": 5},
    {"name": "Jake Elliott",       "position": "K",   "nfl_team": "PHI", "adp": 148, "projected_points": 145, "bye_week": 5},

    # ── DSTs ────────────────────────────────────────────────────────────────
    {"name": "San Francisco 49ers","position": "DEF", "nfl_team": "SF",  "adp": 60,  "projected_points": 140, "bye_week": 9},
    {"name": "Dallas Cowboys",     "position": "DEF", "nfl_team": "DAL", "adp": 65,  "projected_points": 132, "bye_week": 7},
    {"name": "Baltimore Ravens",   "position": "DEF", "nfl_team": "BAL", "adp": 62,  "projected_points": 136, "bye_week": 14},
    {"name": "Philadelphia Eagles","position": "DEF", "nfl_team": "PHI", "adp": 68,  "projected_points": 128, "bye_week": 5},
]

# Historical bid data: (player_name, season, bid) tuples
# Used to populate draft_picks for seasons 2023-2025 so build_rankings_from_db works
_HIST_BIDS: list[tuple[str, int, int]] = [
    # 2023
    ("Christian McCaffrey", 2023, 72), ("Ja'Marr Chase", 2023, 52), ("Justin Jefferson", 2023, 50),
    ("Travis Kelce", 2023, 48), ("Tyreek Hill", 2023, 46), ("CeeDee Lamb", 2023, 44),
    ("Josh Allen", 2023, 55), ("Lamar Jackson", 2023, 42), ("Derrick Henry", 2023, 30),
    ("A.J. Brown", 2023, 38), ("Davante Adams", 2023, 35), ("Mark Andrews", 2023, 33),
    ("Bijan Robinson", 2023, 28), ("De'Von Achane", 2023, 20), ("Amon-Ra St. Brown", 2023, 32),
    # 2024
    ("Christian McCaffrey", 2024, 76), ("Ja'Marr Chase", 2024, 57), ("Justin Jefferson", 2024, 54),
    ("Travis Kelce", 2024, 52), ("Tyreek Hill", 2024, 48), ("CeeDee Lamb", 2024, 62),
    ("Josh Allen", 2024, 60), ("Lamar Jackson", 2024, 55), ("Bijan Robinson", 2024, 40),
    ("Breece Hall", 2024, 38), ("De'Von Achane", 2024, 32), ("Sam LaPorta", 2024, 25),
    ("Puka Nacua", 2024, 28), ("Jaylen Waddle", 2024, 35), ("Amon-Ra St. Brown", 2024, 38),
    # 2025
    ("Christian McCaffrey", 2025, 71), ("Ja'Marr Chase", 2025, 62), ("CeeDee Lamb", 2025, 68),
    ("Justin Jefferson", 2025, 58), ("Lamar Jackson", 2025, 62), ("Josh Allen", 2025, 65),
    ("Brock Purdy", 2025, 45), ("Travis Kelce", 2025, 50), ("Trey McBride", 2025, 30),
    ("Breece Hall", 2025, 44), ("Jahmyr Gibbs", 2025, 36), ("Kyren Williams", 2025, 33),
    ("A.J. Brown", 2025, 42), ("Stefon Diggs", 2025, 32), ("Drake London", 2025, 28),
]

# DraftValue auction figures for the 2026 season (consensus from aggregated sources)
_DRAFT_VALUES_2026: dict[str, float] = {
    "Christian McCaffrey": 72.0, "Lamar Jackson": 65.0, "Josh Allen": 62.0,
    "Ja'Marr Chase": 60.0, "CeeDee Lamb": 58.0, "Justin Jefferson": 55.0,
    "Brock Purdy": 46.0, "Jalen Hurts": 48.0, "Travis Kelce": 52.0,
    "Tyreek Hill": 46.0, "Breece Hall": 42.0, "Bijan Robinson": 44.0,
    "De'Von Achane": 38.0, "A.J. Brown": 42.0, "Amon-Ra St. Brown": 40.0,
    "Jahmyr Gibbs": 36.0, "Kyren Williams": 34.0, "Trey McBride": 30.0,
    "Jaylen Waddle": 36.0, "Davante Adams": 28.0, "Puka Nacua": 26.0,
    "Mark Andrews": 28.0, "Derrick Henry": 24.0, "Sam LaPorta": 24.0,
    "Travis Etienne": 22.0, "Tony Pollard": 20.0, "Stefon Diggs": 28.0,
    "Drake London": 26.0, "Joe Mixon": 22.0, "Aaron Jones": 18.0,
    "Josh Jacobs": 4.0,   # IR – effectively $0 for draft purposes
    "Tua Tagovailoa": 20.0, "Sam Darnold": 16.0, "CJ Stroud": 32.0,
    "Dak Prescott": 28.0, "Breece Hall": 42.0, "Dalton Kincaid": 14.0,
    "Kyle Pitts": 18.0, "David Njoku": 16.0, "Evan Engram": 17.0,
    "Mike Evans": 21.0, "Chris Olave": 20.0, "Deebo Samuel": 16.0,
    "Justin Tucker": 12.0, "Evan McPherson": 11.0, "Brandon McManus": 10.0,
    "Jake Elliott": 11.0,
    "San Francisco 49ers": 10.0, "Dallas Cowboys": 9.0,
    "Baltimore Ravens": 9.5, "Philadelphia Eagles": 9.0,
}


def _upsert_player(db, p: dict):
    from backend import models
    existing = db.query(models.Player).filter(models.Player.name == p["name"]).first()
    if existing:
        for col in ("position", "nfl_team", "adp", "projected_points", "bye_week",
                    "espn_id", "injury_status", "injury_notes",
                    "projected_return_date", "projected_return_week"):
            val = p.get(col)
            if val is not None:
                setattr(existing, col, val)
        return existing
    player = models.Player(
        name=p["name"],
        position=p.get("position"),
        nfl_team=p.get("nfl_team"),
        adp=float(p.get("adp", 0)),
        projected_points=float(p.get("projected_points", 0)),
        bye_week=p.get("bye_week"),
        espn_id=p.get("espn_id"),
        injury_status=p.get("injury_status"),
        injury_notes=p.get("injury_notes"),
        projected_return_date=p.get("projected_return_date"),
        projected_return_week=p.get("projected_return_week"),
    )
    db.add(player)
    return player


def seed(
    league_id: int = 1,
    season: int = 2026,
    reset: bool = False,
) -> None:
    from backend.database import SessionLocal
    from backend.core.security import get_password_hash
    from backend import models
    import backend.models_draft_value as dv

    db = SessionLocal()
    try:
        league = db.query(models.League).filter(models.League.id == league_id).first()
        if not league:
            print(f"ERROR: League {league_id} not found. Run the startup seeder first.", file=sys.stderr)
            sys.exit(1)

        # ------------------------------------------------------------------ #
        # 1. Remove UAT owners if resetting
        # ------------------------------------------------------------------ #
        if reset:
            uat_usernames = [o["username"] for o in _OWNERS]
            uat_users = db.query(models.User).filter(models.User.username.in_(uat_usernames)).all()
            for u in uat_users:
                db.query(models.DraftPick).filter(models.DraftPick.owner_id == u.id).delete()
            db.query(models.User).filter(models.User.username.in_(uat_usernames)).delete()
            db.commit()
            print("UAT owners and their draft picks cleared.")

        # ------------------------------------------------------------------ #
        # 2. Upsert 10 team owners
        # ------------------------------------------------------------------ #
        owner_objs: list[models.User] = []
        for o in _OWNERS:
            existing = db.query(models.User).filter(models.User.username == o["username"]).first()
            if not existing:
                user = models.User(
                    username=o["username"],
                    email=o["email"],
                    hashed_password=get_password_hash("password"),
                    is_commissioner=False,
                    is_superuser=False,
                    league_id=league_id,
                    team_name=o["team_name"],
                )
                db.add(user)
                db.flush()
                owner_objs.append(user)
                print(f"  Created owner: {o['username']} ({o['team_name']})")
            else:
                existing.league_id = league_id
                existing.team_name = o["team_name"]
                owner_objs.append(existing)
                print(f"  Updated owner: {o['username']}")
        db.commit()
        for u in owner_objs:
            db.refresh(u)

        # ------------------------------------------------------------------ #
        # 3. Upsert players
        # ------------------------------------------------------------------ #
        player_map: dict[str, models.Player] = {}
        for p_data in _PLAYERS:
            player = _upsert_player(db, p_data)
            db.flush()
            player_map[p_data["name"]] = player
        db.commit()
        for name, p in player_map.items():
            db.refresh(p)
        print(f"  Players upserted: {len(player_map)}")

        # ------------------------------------------------------------------ #
        # 4. Historical draft picks (2023-2025) — needed for historical
        #    rankings to have bid data to compute model_score from
        # ------------------------------------------------------------------ #
        num_owners = len(owner_objs)
        inserted_picks = 0
        for idx, (player_name, pick_season, bid) in enumerate(_HIST_BIDS):
            player = player_map.get(player_name)
            if not player:
                continue
            # Rotate owner assignment evenly across UAT owners
            owner = owner_objs[idx % num_owners]
            existing_pick = (
                db.query(models.DraftPick)
                .filter(
                    models.DraftPick.player_id == player.id,
                    models.DraftPick.year == pick_season,
                    models.DraftPick.league_id == league_id,
                )
                .first()
            )
            if not existing_pick:
                pick = models.DraftPick(
                    player_id=player.id,
                    owner_id=owner.id,
                    league_id=league_id,
                    year=pick_season,
                    amount=bid,
                    session_id=f"uat-{pick_season}",
                    current_status="BENCH",
                )
                db.add(pick)
                inserted_picks += 1
        db.commit()
        print(f"  Historical picks inserted: {inserted_picks}")

        # ------------------------------------------------------------------ #
        # 5. DraftValue rows for 2026 (consensus auction values)
        # ------------------------------------------------------------------ #
        now_str = datetime.now(timezone.utc).isoformat()
        inserted_dv = 0
        for player_name, auction_value in _DRAFT_VALUES_2026.items():
            player = player_map.get(player_name)
            if not player:
                continue
            existing_dv = (
                db.query(dv.DraftValue)
                .filter(
                    dv.DraftValue.player_id == player.id,
                    dv.DraftValue.season == season,
                )
                .first()
            )
            vor = max(0.0, auction_value - 10.0)  # simplified VOR baseline
            tier = (
                "S" if auction_value >= 55 else
                "A" if auction_value >= 35 else
                "B" if auction_value >= 20 else
                "C" if auction_value >= 10 else
                "D"
            )
            if existing_dv:
                existing_dv.avg_auction_value = auction_value
                existing_dv.value_over_replacement = vor
                existing_dv.consensus_tier = tier
                existing_dv.last_updated = now_str
            else:
                db.add(dv.DraftValue(
                    player_id=player.id,
                    season=season,
                    avg_auction_value=auction_value,
                    median_adp=player.adp,
                    value_over_replacement=vor,
                    consensus_tier=tier,
                    last_updated=now_str,
                ))
                inserted_dv += 1
        db.commit()
        print(f"  DraftValue rows upserted: {inserted_dv} new, {len(_DRAFT_VALUES_2026) - inserted_dv} updated")

        # ------------------------------------------------------------------ #
        # 6. Set league draft_status to LIVE_DRAFT for UAT
        # ------------------------------------------------------------------ #
        league.draft_status = "LIVE_DRAFT"
        db.commit()
        print(f"  League '{league.name}' draft_status → LIVE_DRAFT")

        print()
        print("UAT draft board seed complete.")
        print(f"  Owners: {len(owner_objs)} (username pattern: uat_owner_01…10, password: password)")
        print(f"  Players: {len(player_map)}")
        print(f"  Injured players: {sum(1 for p in _PLAYERS if p.get('injury_status'))}")
        print(f"  DraftValue season: {season}")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league-id", type=int, default=1, help="Target league (default: 1)")
    parser.add_argument("--season",    type=int, default=2026, help="DraftValue season year (default: 2026)")
    parser.add_argument("--reset",     action="store_true", help="Delete existing UAT owners/picks first")
    args = parser.parse_args()
    seed(league_id=args.league_id, season=args.season, reset=args.reset)
