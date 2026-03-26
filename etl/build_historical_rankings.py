from __future__ import annotations

import argparse
from pathlib import Path

from etl.load.load_to_postgres import load_historical_rankings_to_db
from etl.transform.historical_rankings import (
    build_rankings_from_db,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build historical league-based draft rankings from database data and optionally load into DraftValue table."
    )
    parser.add_argument(
        "--season",
        type=int,
        required=True,
        help="Target season for generated rankings.",
    )
    parser.add_argument(
        "--output",
        default="backend/exports/historical_rankings.csv",
        help="Output CSV path for rankings.",
    )
    parser.add_argument(
        "--load-db",
        action="store_true",
        help="Load generated rankings into DraftValue table.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import sys
    from pathlib import Path as _Path

    sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    from backend.database import SessionLocal  # type: ignore[import]

    db = SessionLocal()
    try:
        result = build_rankings_from_db(db, target_season=args.season)
    finally:
        db.close()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.rankings.to_csv(output_path, index=False)
    print(f"Historical rankings written to {output_path} ({len(result.rankings)} players)")

    if args.load_db:
        load_historical_rankings_to_db(result.rankings, season=args.season)
        print("Historical rankings loaded into DraftValue table")


if __name__ == "__main__":
    main()

