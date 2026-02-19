import sys
import os
from datetime import datetime
import time
import requests
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models

# Add the parent directory (backend) to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"

ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K"}


def get_json(url, params=None, timeout=30):
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_event_ids(season, week, season_type=2):
    params = {
        "year": season,
        "week": week,
        "seasontype": season_type,
    }
    data = get_json(ESPN_SCOREBOARD_URL, params=params)
    return [event.get("id") for event in data.get("events", []) if event.get("id")]


def parse_stats_from_summary(summary_json):
    results = []
    players = summary_json.get("boxscore", {}).get("players", [])

    for team_group in players:
        team = team_group.get("team", {})
        team_abbr = team.get("abbreviation")
        for stat_group in team_group.get("statistics", []):
            labels = stat_group.get("labels", [])
            athletes = stat_group.get("athletes", [])
            for athlete in athletes:
                athlete_id = athlete.get("id")
                name = athlete.get("displayName")
                position = athlete.get("position", {}).get("abbreviation")
                stats = athlete.get("stats", [])

                if not athlete_id or not name or not position:
                    continue
                if position not in ALLOWED_POSITIONS:
                    continue

                stats_map = {label: stats[idx] for idx, label in enumerate(labels) if idx < len(stats)}
                results.append({
                    "espn_id": str(athlete_id),
                    "name": name,
                    "position": position,
                    "team": team_abbr,
                    "stats": stats_map,
                })

    return results


def resolve_player(db: Session, espn_id, name, position, team_abbr):
    player = db.query(models.Player).filter(models.Player.espn_id == espn_id).first()
    if player:
        return player

    player = models.Player(
        name=name,
        position=position,
        nfl_team=team_abbr,
        espn_id=espn_id,
        bye_week=None,
    )
    db.add(player)
    db.flush()
    return player


def store_weekly_stat(db: Session, player, season, week, stats_map, source="espn"):
    fantasy_points = None
    for key in ("fantasyPoints", "fantasyPointsPPR", "fantasyPoints_ppr"):
        if key in stats_map:
            try:
                fantasy_points = float(stats_map[key])
            except (TypeError, ValueError):
                fantasy_points = None
            break

    existing = db.query(models.PlayerWeeklyStat).filter(
        models.PlayerWeeklyStat.player_id == player.id,
        models.PlayerWeeklyStat.season == season,
        models.PlayerWeeklyStat.week == week,
        models.PlayerWeeklyStat.source == source,
    ).first()

    if existing:
        existing.stats = stats_map
        existing.fantasy_points = fantasy_points
        existing.created_at = datetime.utcnow().isoformat()
        return False

    entry = models.PlayerWeeklyStat(
        player_id=player.id,
        season=season,
        week=week,
        fantasy_points=fantasy_points,
        stats=stats_map,
        source=source,
        created_at=datetime.utcnow().isoformat(),
    )
    db.add(entry)
    return True


def archive_week(season, week, season_type=2):
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        event_ids = fetch_event_ids(season, week, season_type=season_type)
        print(f"📅 ESPN events for {season} week {week}: {len(event_ids)}")

        created = 0
        updated = 0
        for event_id in event_ids:
            summary = get_json(ESPN_SUMMARY_URL, params={"event": event_id})
            stats = parse_stats_from_summary(summary)

            for item in stats:
                player = resolve_player(
                    db,
                    item["espn_id"],
                    item["name"],
                    item["position"],
                    item["team"],
                )
                if store_weekly_stat(db, player, season, week, item["stats"]):
                    created += 1
                else:
                    updated += 1

            time.sleep(0.1)

        db.commit()
        print(f"✅ Archived weekly stats: {created} added, {updated} updated")
    except Exception as exc:
        db.rollback()
        print(f"❌ Weekly archive failed: {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python archive_weekly_stats.py <season> <week>")
        sys.exit(1)

    season_arg = int(sys.argv[1])
    week_arg = int(sys.argv[2])
    archive_week(season_arg, week_arg)
