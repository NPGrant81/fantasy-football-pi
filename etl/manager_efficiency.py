"""Backfill / weekly ETL job for manager efficiency metrics.

This module is intended to be executed once per week (e.g. via cron) after the
latest scores have been finalized.  It relies on the `roster_history` table to
provide an immutable snapshot of each owner's roster & starter designation for
that week.  If `roster_history` does not yet exist the script will simply
log a warning and exit; the data model will be added as part of the analytics
infrastructure story (#44) and this code can be updated accordingly.

The script populates the `manager_efficiency` table defined by the
`ManagerEfficiency` ORM model.  Duplicate rows are upserted so the job may be
re-run safely.

Usage::
    python etl/manager_efficiency.py --season 2026 --week 5

"""

import logging
import sys
from argparse import ArgumentParser

# fix path so backend package is importable
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import SessionLocal
from backend import models
from backend.utils.efficiency import calculate_optimal_score

logger = logging.getLogger("etl.manager_efficiency")
logging.basicConfig(level=logging.INFO)


def process_week(season: int, week: int):
    db = SessionLocal()
    try:
        # attempt to query roster_history; if table missing, abort gracefully
        if not db.bind.dialect.has_table(db.bind, "roster_history"):
            logger.warning("roster_history table not found; skipping efficiency calculation")
            return

        # league settings may be stored in league_settings (JSON field)
        # fetch all distinct (league_id, owner_id) for the week
        rows = db.execute(
            "SELECT DISTINCT league_id, owner_id FROM roster_history WHERE season = :s AND week = :w",
            {"s": season, "w": week},
        ).fetchall()

        for league_id, owner_id in rows:
            # grab league roster for the week
            roster = db.execute(
                "SELECT * FROM roster_history WHERE season = :s AND week = :w "
                "AND league_id = :l AND owner_id = :o",
                {"s": season, "w": week, "l": league_id, "o": owner_id},
            ).mappings().all()

            if not roster:
                continue

            # convert to list of dicts expected by calculate_optimal_score
            roster_list = []
            for r in roster:
                roster_list.append({
                    "player_id": r["player_id"],
                    "position": r.get("position"),
                    "actual_score": r.get("points", 0),
                    "is_ir": r.get("is_ir", False),
                    "is_taxi": r.get("is_taxi", False),
                })

            # fetch settings for league
            settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league_id).first()
            slots = settings.starting_slots if settings else {}

            optimal, optimal_lineup = calculate_optimal_score(roster_list, {"starting_slots": slots}, return_lineup=True)
            actual = sum(p["actual_score"] for p in roster_list if p.get("is_starter") or False)
            efficiency = actual / optimal if optimal > 0 else 0

            # upsert
            existing = db.query(models.ManagerEfficiency).filter(
                models.ManagerEfficiency.league_id == league_id,
                models.ManagerEfficiency.manager_id == owner_id,
                models.ManagerEfficiency.season == season,
                models.ManagerEfficiency.week == week,
            ).first()

            if existing:
                existing.actual_points_total = actual
                existing.optimal_points_total = optimal
                existing.points_left_on_bench = optimal - actual
                existing.efficiency_rating = efficiency
                existing.optimal_lineup_json = optimal_lineup
            else:
                db.add(models.ManagerEfficiency(
                    league_id=league_id,
                    manager_id=owner_id,
                    season=season,
                    week=week,
                    actual_points_total=actual,
                    optimal_points_total=optimal,
                    points_left_on_bench=optimal - actual,
                    efficiency_rating=efficiency,
                    optimal_lineup_json=optimal_lineup,
                ))
        db.commit()
        logger.info(f"Processed efficiency for season {season} week {week}")
    except Exception:
        logger.exception("error processing efficiency")
    finally:
        db.close()


def main():
    parser = ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()
    process_week(args.season, args.week)


if __name__ == "__main__":
    main()
