"""Pre-production Yahoo auth and payload quality gate.

Performs a live read-only Yahoo API call and validates basic data quality.
No database writes are performed.
"""

from __future__ import annotations

import argparse

import pandas as pd

from etl.extract.extract_yahoo import fetch_yahoo_top_players, transform_yahoo_players
from etl.extract.extract_yahoo_precheck import evaluate_yahoo_quality


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Yahoo pre-prod auth and quality checks.")
    parser.add_argument("--max-players", type=int, default=100)
    parser.add_argument("--min-players", type=int, default=50)
    parser.add_argument("--min-adp-coverage", type=float, default=0.80)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        players = fetch_yahoo_top_players(max_players=args.max_players)
        norm_df = pd.DataFrame(transform_yahoo_players(players)) if players else pd.DataFrame()
    except Exception as exc:
        print(f"FAIL: Yahoo auth/request error: {exc}")
        return 2

    report = evaluate_yahoo_quality(
        norm_df,
        min_players=args.min_players,
        min_adp_coverage=args.min_adp_coverage,
    )

    print("Yahoo pre-prod quality report")
    print(f"- total_rows: {report.total_rows}")
    print(f"- adp_rows: {report.adp_rows}")
    print(f"- adp_coverage: {report.adp_coverage:.1%}")

    if report.passed:
        print("PASS: Yahoo auth/data quality thresholds satisfied.")
        return 0

    print("FAIL: Yahoo quality thresholds not satisfied.")
    for error in report.errors:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())