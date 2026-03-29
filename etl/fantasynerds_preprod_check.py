"""Pre-production FantasyNerds quality gate.

Runs a live read-only API call and validates row count + value coverage.
No database writes are performed.
"""

from __future__ import annotations

import argparse
import os
import sys

from etl.extract.extract_fantasynerds import (
    evaluate_fantasynerds_quality,
    fetch_fantasynerds_auction_values,
    transform_fantasynerds_auction_values,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FantasyNerds pre-prod quality checks.")
    parser.add_argument("--api-key", default=os.getenv("FANTASYNERDS_API_KEY"))
    parser.add_argument("--teams", type=int, default=12)
    parser.add_argument("--budget", type=int, default=200)
    parser.add_argument("--format", dest="scoring_format", default="ppr", choices=["std", "ppr"])
    parser.add_argument("--min-players", type=int, default=150)
    parser.add_argument("--min-auction-coverage", type=float, default=0.80)
    parser.add_argument("--min-minmax-coverage", type=float, default=0.50)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.api_key:
        print("FAIL: missing API key (use --api-key or FANTASYNERDS_API_KEY).")
        return 2

    try:
        raw_df = fetch_fantasynerds_auction_values(
            args.api_key,
            teams=args.teams,
            budget=args.budget,
            scoring_format=args.scoring_format,
        )
        norm_df = transform_fantasynerds_auction_values(raw_df)
        report = evaluate_fantasynerds_quality(
            norm_df,
            min_players=args.min_players,
            min_auction_coverage=args.min_auction_coverage,
            min_minmax_coverage=args.min_minmax_coverage,
        )
    except Exception as exc:
        print(f"FAIL: request/parse error: {exc}")
        return 2

    print("FantasyNerds pre-prod quality report")
    print(f"- total_rows: {report.total_rows}")
    print(f"- auction_value_rows: {report.auction_value_rows}")
    print(f"- minmax_rows: {report.minmax_rows}")
    print(f"- auction_coverage: {report.auction_coverage:.1%}")
    print(f"- minmax_coverage: {report.minmax_coverage:.1%}")

    if report.passed:
        print("PASS: source quality thresholds satisfied.")
        return 0

    print("FAIL: source quality thresholds not satisfied.")
    for error in report.errors:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())