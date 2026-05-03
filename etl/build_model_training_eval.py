from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from etl.modeling.training_pipeline import SplitPolicy, evaluate_candidates, write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Issue #108 model training/evaluation scaffold with time-based split and report export."
    )
    parser.add_argument("--input-csv", required=True, help="Input dataset CSV path with season_year and target column.")
    parser.add_argument("--target-col", default="winning_bid", help="Target column to evaluate.")
    parser.add_argument(
        "--feature-cols",
        default="",
        help="Comma-separated feature columns. Empty uses all numeric columns except season_year and target.",
    )
    parser.add_argument("--train-end-season", type=int, required=True, help="Inclusive train end season.")
    parser.add_argument("--val-season", type=int, required=True, help="Validation season year.")
    parser.add_argument("--test-season", type=int, required=True, help="Test season year.")
    parser.add_argument(
        "--output-dir",
        default="etl/outputs/model_eval",
        help="Directory for evaluation artifacts.",
    )
    return parser.parse_args()


def _resolve_feature_cols(df: pd.DataFrame, target_col: str, raw_cols: str) -> list[str]:
    if raw_cols.strip():
        return [col.strip() for col in raw_cols.split(",") if col.strip()]

    numeric_cols = set(df.select_dtypes(include=["number"]).columns.tolist())
    excluded = {"season_year", target_col}
    return sorted(list(numeric_cols - excluded))


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_csv)
    df = pd.read_csv(input_path)

    if "season_year" not in df.columns:
        raise ValueError("Input CSV must include season_year column for time-based split.")
    if args.target_col not in df.columns:
        raise ValueError(f"Input CSV missing target column: {args.target_col}")

    feature_cols = _resolve_feature_cols(df, args.target_col, args.feature_cols)
    split = SplitPolicy(
        train_end_season=args.train_end_season,
        val_season=args.val_season,
        test_season=args.test_season,
    )
    report = evaluate_candidates(
        df=df,
        split=split,
        target_col=args.target_col,
        feature_cols=feature_cols,
    )

    report_path = write_report(report, output_dir=Path(args.output_dir))
    print(f"Model evaluation report written to {report_path}")


if __name__ == "__main__":
    main()
