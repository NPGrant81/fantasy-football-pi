"""Import NFL schedule data from ESPN into the local database.

Usage:
    python import_nfl_schedule.py <year> [<week>]

If <week> is specified the script fetches the weekly schedule; otherwise it
retrieves the full scoreboard for the year and processes every event.  The
`nfl_games` table (see models.NFLGame) is upserted by event_id so the script
can safely be run repeatedly as scores update.
"""
import sys
import os
import requests

# ensure backend package is on sys.path when running from repository root
# (calling scripts from other directories, CI tasks, etc.)
root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root not in sys.path:
    sys.path.insert(0, root)

from database import SessionLocal
import models


def fetch_scoreboard(year: int, week: int | None = None) -> dict:
    if week is None:
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?limit=1000&dates={year}"
    else:
        url = f"https://cdn.espn.com/core/nfl/schedule?xhr=1&year={year}&week={week}"
    print(f"Fetching {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()



from datetime import datetime, timedelta

def estimate_week_from_date(date_str: str) -> int | None:
    """Try to guess the NFL week given a kickoff ISO timestamp.

    Uses the first Thursday of September as week 1 and counts full weeks
    thereafter.  Returns None if the date is before that start.
    """
    try:
        dt = datetime.fromisoformat(date_str.rstrip("Z"))
    except Exception:
        return None
    # find first Thursday of September in that year
    sep1 = datetime(dt.year, 9, 1)
    days_until_thu = (3 - sep1.weekday()) % 7
    season_start = sep1 + timedelta(days=days_until_thu)
    if dt < season_start:
        return None
    week = ((dt - season_start).days // 7) + 1
    return week


def normalize_event(evt: dict) -> dict:
    comp = evt.get("competitions", [])[0]
    week_num = comp.get("week", {}).get("number")
    # fallback to estimation if ESPN omitted week
    if week_num is None:
        kickoff = comp.get("date")
        if kickoff:
            week_num = estimate_week_from_date(kickoff)
    home = comp.get("competitors", [])[0]
    away = comp.get("competitors", [])[1]
    return {
        "event_id": evt.get("id"),
        "season": evt.get("season", {}).get("year"),
        "week": week_num,
        "home_team_id": home.get("team", {}).get("id"),
        "away_team_id": away.get("team", {}).get("id"),
        "kickoff": comp.get("date"),
        "status": comp.get("status", {}).get("type", {}).get("name"),
        "home_score": int(home.get("score") or 0),
        "away_score": int(away.get("score") or 0),
    }


def upsert_games(year: int, week: int | None = None) -> None:
    data = fetch_scoreboard(year, week)
    events = data.get("events", [])
    db = SessionLocal()
    try:
        for evt in events:
            vals = normalize_event(evt)
            if not vals.get("event_id"):
                continue
            game = (
                db.query(models.NFLGame)
                .filter(models.NFLGame.event_id == vals["event_id"])
                .one_or_none()
            )
            if game:
                for key, val in vals.items():
                    setattr(game, key, val)
            else:
                db.add(models.NFLGame(**vals))
        db.commit()
        print(f"Upserted {len(events)} events")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_nfl_schedule.py <year> [<week>]")
        sys.exit(1)
    year = int(sys.argv[1])
    week = int(sys.argv[2]) if len(sys.argv) > 2 else None
    upsert_games(year, week)
