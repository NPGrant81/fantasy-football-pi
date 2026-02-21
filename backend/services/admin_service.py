# backend/services/admin_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException
import models
from core import security

# --- 1.1 LEAGUE MANAGEMENT (COMMISSIONER) ---

def finalize_league_draft(db: Session, league_id: int):
    # 1.1.1 Logic to lock the draft
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league: raise HTTPException(status_code=404, detail="League not found")
    league.draft_status = "COMPLETED"
    db.commit()
    return league

def reset_league_rosters(db: Session, league_id: int):
    # 1.1.2 Nuclear reset for a specific league
    db.query(models.DraftPick).filter(models.DraftPick.league_id == league_id).delete()
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if league: league.draft_status = "PRE_DRAFT"
    db.commit()
    return {"status": "success"}

# --- 1.2 PLATFORM TOOLS (SUPERUSER) ---

def create_full_test_league(db: Session):
    # 1.2.1 Logic moved from your router's "create-test-league"
    league_name = "Test League 2026"
    league = models.League(name=league_name)
    db.add(league)
    db.commit()
    db.refresh(league)
    
    # 1.2.2 Add dummy owners logic... (omitted for brevity but keep your code here!)
    return league

def sync_initial_nfl_data(db: Session):
    """
    Sync NFL player data from ESPN API.
    This imports or updates all active roster players in the allowed fantasy positions.
    """
    import time
    import requests
    
    ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
    ESPN_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster"
    ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}
    
    def get_json(url, params=None, timeout=30):
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    
    def fetch_team_list():
        data = get_json(ESPN_TEAMS_URL)
        sports = data.get("sports", [])
        leagues = sports[0].get("leagues", []) if sports else []
        teams = leagues[0].get("teams", []) if leagues else []
        parsed = []
        for team in teams:
            team_data = team.get("team", {})
            team_id = team_data.get("id")
            abbr = team_data.get("abbreviation")
            if team_id and abbr:
                parsed.append({"id": team_id, "abbr": abbr})
        return parsed
    
    def iter_roster_athletes(roster_json):
        groups = roster_json.get("athletes", [])
        for group in groups:
            for athlete in group.get("items", []):
                yield athlete
    
    def upsert_player(name, position, team_abbr, espn_id):
        existing = db.query(models.Player).filter(models.Player.espn_id == espn_id).first()
        if existing:
            existing.name = name
            existing.position = position
            existing.nfl_team = team_abbr
            return existing, False
        player = models.Player(
            name=name, position=position, nfl_team=team_abbr,
            espn_id=espn_id, bye_week=None,
        )
        db.add(player)
        return player, True
    
    def upsert_defense(team_abbr):
        espn_id = f"DEF_{team_abbr}"
        existing = db.query(models.Player).filter(models.Player.espn_id == espn_id).first()
        if existing:
            existing.name = f"{team_abbr} Defense"
            existing.position = "DEF"
            existing.nfl_team = team_abbr
            return False
        defense = models.Player(
            name=f"{team_abbr} Defense", position="DEF", nfl_team=team_abbr,
            espn_id=espn_id, bye_week=None,
        )
        db.add(defense)
        return True
    
    try:
        teams = fetch_team_list()
        added = updated = skipped = def_added = 0
        
        for team in teams:
            team_id = team["id"]
            team_abbr = team["abbr"]
            roster = get_json(ESPN_ROSTER_URL.format(team_id=team_id))
            
            for athlete in iter_roster_athletes(roster):
                position = athlete.get("position", {}).get("abbreviation")
                if position not in ALLOWED_POSITIONS:
                    skipped += 1
                    continue
                espn_id = athlete.get("id")
                name = athlete.get("fullName") or athlete.get("displayName")
                if not espn_id or not name:
                    skipped += 1
                    continue
                _, created = upsert_player(name, position, team_abbr, str(espn_id))
                if created:
                    added += 1
                else:
                    updated += 1
            
            if upsert_defense(team_abbr):
                def_added += 1
            time.sleep(0.1)
        
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(exc)}")