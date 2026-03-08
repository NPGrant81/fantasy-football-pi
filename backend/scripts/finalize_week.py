from __future__ import annotations

import argparse
from datetime import datetime, timezone

from backend.database import SessionLocal
from backend.services.week_finalization_service import finalize_league_week


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize one league week: lock matchup scores and refresh standings snapshot."
    )
    parser.add_argument("--league-id", type=int, required=True, help="Target league ID")
    parser.add_argument("--week", type=int, required=True, help="Week number to finalize")
    parser.add_argument(
        "--season",
        type=int,
        default=datetime.now(timezone.utc).year,
        help="Stat season used for weekly points lookup",
    )
    parser.add_argument(
        "--season-year",
        type=int,
        default=None,
        help="Optional scoring season year for league-specific rules",
    )
    return parser.parse_args()


def run_finalization(*, league_id: int, week: int, season: int, season_year: int | None = None) -> dict:
    db = SessionLocal()
    try:
        result = finalize_league_week(
            db,
            league_id=league_id,
            week=week,
            season=season,
            season_year=season_year,
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    args = parse_args()
    result = run_finalization(
        league_id=args.league_id,
        week=args.week,
        season=args.season,
        season_year=args.season_year,
    )

    print(
        f"Finalized league={result['league_id']} week={result['week']} "
        f"matchups={result['matchups_finalized']}"
    )
    if result["standings"]:
        top = result["standings"][0]
        print(
            f"Current leader: {top['team_name']} "
            f"({top['wins']}-{top['losses']}-{top['ties']}, PF={top['points_for']})"
        )


if __name__ == "__main__":
    main()
