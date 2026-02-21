#!/usr/bin/env python
"""
UAT Sync: Complete fresh reset and reimport of NFL player data.
This script:
1. Clears all draft picks (to avoid FK constraints)
2. Deletes all players
3. Reimports fresh player data from ESPN API
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine
import models
import time
import requests

def run_uat_sync():
    """Complete UAT reset and sync of player data."""
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # Step 1: Clear draft picks
        print("=" * 60)
        print("STEP 1: Clearing draft picks...")
        print("=" * 60)
        pick_count = db.query(models.DraftPick).count()
        if pick_count > 0:
            db.query(models.DraftPick).delete()
            db.commit()
            print(f"✅ Deleted {pick_count} draft picks")
        else:
            print("✅ No draft picks to delete")
        
        # Step 1b: Clear trade proposals (they reference players)
        print("\n" + "=" * 60)
        print("STEP 1b: Clearing trade proposals...")
        print("=" * 60)
        from sqlalchemy import text
        try:
            trade_count = db.query(models.TradeProposal).count() if hasattr(models, 'TradeProposal') else 0
            if trade_count > 0:
                db.query(models.TradeProposal).delete()
                db.commit()
                print(f"✅ Deleted {trade_count} trade proposals")
            else:
                print("✅ No trade proposals to delete")
        except:
            # If TradeProposal doesn't exist or can't be queried, use raw SQL
            try:
                db.execute(text("DELETE FROM trade_proposals"))
                db.commit()
                print("✅ Cleared trade_proposals table")
            except:
                print("ℹ️  No trade_proposals table or already empty")
        
        # Step 2: Clear players
        print("\n" + "=" * 60)
        print("STEP 2: Clearing all players...")
        print("=" * 60)
        player_count = db.query(models.Player).count()
        if player_count > 0:
            db.query(models.Player).delete()
            db.commit()
            print(f"✅ Deleted {player_count} players")
        else:
            print("✅ No players to delete")
        
        # Step 3: Reimport from ESPN
        print("\n" + "=" * 60)
        print("STEP 3: Reimporting players from ESPN API...")
        print("=" * 60)
        
        ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
        ESPN_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster"
        ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}
        
        def get_json(url, params=None, timeout=30):
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        
        def upsert_player(name, position, team_abbr, espn_id):
            player = models.Player(
                name=name, position=position, nfl_team=team_abbr,
                espn_id=espn_id, bye_week=None,
            )
            db.add(player)
            db.flush()
            return True
        
        def upsert_defense(team_abbr):
            espn_id = f"DEF_{team_abbr}"
            defense = models.Player(
                name=f"{team_abbr} Defense", position="DEF", nfl_team=team_abbr,
                espn_id=espn_id, bye_week=None,
            )
            db.add(defense)
            db.flush()
            return True
        
        # Fetch teams
        print("Fetching 32 NFL teams...")
        data = get_json(ESPN_TEAMS_URL)
        sports = data.get("sports", [])
        leagues = sports[0].get("leagues", []) if sports else []
        teams = leagues[0].get("teams", []) if leagues else []
        
        team_list = []
        for team in teams:
            team_data = team.get("team", {})
            team_id = team_data.get("id")
            abbr = team_data.get("abbreviation")
            if team_id and abbr:
                team_list.append({"id": team_id, "abbr": abbr})
        
        print(f"✅ Found {len(team_list)} teams\n")
        
        added = updated = skipped = def_added = 0
        
        # Import rosters
        for i, team in enumerate(team_list, 1):
            team_id = team["id"]
            team_abbr = team["abbr"]
            print(f"[{i:2d}/32] Importing {team_abbr}...", end=" ", flush=True)
            
            try:
                roster = get_json(ESPN_ROSTER_URL.format(team_id=team_id))
                athletes = roster.get("athletes", [])
                
                team_added = 0
                for group in athletes:
                    for athlete in group.get("items", []):
                        position = athlete.get("position", {}).get("abbreviation")
                        if position not in ALLOWED_POSITIONS:
                            skipped += 1
                            continue
                        
                        espn_id = athlete.get("id")
                        name = athlete.get("fullName") or athlete.get("displayName")
                        if not espn_id or not name:
                            skipped += 1
                            continue
                        
                        upsert_player(name, position, team_abbr, str(espn_id))
                        team_added += 1
                        added += 1
                
                # Add defense
                upsert_defense(team_abbr)
                def_added += 1
                
                print(f"({team_added} players, 1 DEF) ✅")
            except Exception as e:
                print(f"❌ Error: {e}")
            
            time.sleep(0.15)  # Rate limiting
        
        db.commit()
        
        # Step 4: Summary
        print("\n" + "=" * 60)
        print("STEP 4: Summary")
        print("=" * 60)
        final_count = db.query(models.Player).count()
        print(f"Total players imported: {added}")
        print(f"Defense units added: {def_added}")
        print(f"Players skipped (wrong position): {skipped}")
        print(f"Final player count in database: {final_count}")
        print("\n✅ UAT Sync Complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ UAT Sync Failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_uat_sync()
