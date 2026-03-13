import sys
import os
import time
from datetime import datetime
import requests
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine
import models
from backend.services import player_service
from backend.services.player_identity_service import (
    current_season,
    ensure_primary_alias,
    upsert_player_season,
)

# Add the parent directory (backend) to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
ESPN_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster"

# Only import players in relevant fantasy positions from active NFL rosters
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


def upsert_player(db: Session, name, position, team_abbr, espn_id):
    season = current_season()
    existing = player_service.find_existing_player(
        db,
        espn_id=espn_id,
        name=name,
        position=position,
        nfl_team=team_abbr,
    )
    if existing:
        existing.name = name
        existing.position = position
        existing.nfl_team = team_abbr
        existing.espn_id = str(espn_id)
        upsert_player_season(
            db,
            player_id=int(existing.id),
            season=season,
            nfl_team=team_abbr,
            position=position,
            bye_week=existing.bye_week,
            is_active=True,
            source="espn_roster_sync",
        )
        ensure_primary_alias(db, player_id=int(existing.id), player_name=name)
        return existing, False

    player = models.Player(
        name=name,
        position=position,
        nfl_team=team_abbr,
        espn_id=espn_id,
        bye_week=None,
    )
    db.add(player)
    db.flush()
    upsert_player_season(
        db,
        player_id=int(player.id),
        season=season,
        nfl_team=team_abbr,
        position=position,
        bye_week=player.bye_week,
        is_active=True,
        source="espn_roster_sync",
    )
    ensure_primary_alias(db, player_id=int(player.id), player_name=name)
    return player, True


def upsert_defense(db: Session, team_abbr):
    season = current_season()
    espn_id = f"DEF_{team_abbr}"
    existing = player_service.find_existing_player(
        db,
        espn_id=espn_id,
        name=f"{team_abbr} Defense",
        position="DEF",
        nfl_team=team_abbr,
    )
    if existing:
        existing.name = f"{team_abbr} Defense"
        existing.position = "DEF"
        existing.nfl_team = team_abbr
        existing.espn_id = espn_id
        upsert_player_season(
            db,
            player_id=int(existing.id),
            season=season,
            nfl_team=team_abbr,
            position="DEF",
            bye_week=existing.bye_week,
            is_active=True,
            source="espn_roster_sync",
        )
        ensure_primary_alias(db, player_id=int(existing.id), player_name=existing.name)
        return False

    defense = models.Player(
        name=f"{team_abbr} Defense",
        position="DEF",
        nfl_team=team_abbr,
        espn_id=espn_id,
        bye_week=None,
    )
    db.add(defense)
    db.flush()
    upsert_player_season(
        db,
        player_id=int(defense.id),
        season=season,
        nfl_team=team_abbr,
        position="DEF",
        bye_week=defense.bye_week,
        is_active=True,
        source="espn_roster_sync",
    )
    ensure_primary_alias(db, player_id=int(defense.id), player_name=defense.name)
    return True


def import_active_players():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        teams = fetch_team_list()
        print(f"🏈 ESPN teams found: {len(teams)}")

        added = 0
        updated = 0
        skipped = 0
        def_added = 0

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

                if not player_service.is_valid_fantasy_player(
                    name=name,
                    position=position,
                    nfl_team=team_abbr,
                ):
                    skipped += 1
                    continue

                _, created = upsert_player(db, name, position, team_abbr, str(espn_id))
                if created:
                    added += 1
                else:
                    updated += 1

            if upsert_defense(db, team_abbr):
                def_added += 1

            time.sleep(0.1)

        db.commit()
        print(f"✅ Imported ESPN players: {added} added, {updated} updated, {skipped} skipped")
        print(f"✅ Added defenses: {def_added}")
    except Exception as exc:
        db.rollback()
        print(f"❌ Import failed: {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    import_active_players()
