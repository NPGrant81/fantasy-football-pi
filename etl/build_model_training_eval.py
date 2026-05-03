from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from etl.modeling.training_pipeline import SplitPolicy, evaluate_candidates, write_report
from etl.transform.monte_carlo_simulation import SimulationConfig, run_monte_carlo_draft_simulation


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
    parser.add_argument(
        "--candidate-models",
        default="lightgbm,catboost",
        help="Comma-separated challenger candidates. Optional adapters load only when dependency is installed.",
    )
    parser.add_argument(
        "--champion-model",
        default="baseline_mean",
        help=(
            "Current production champion model used for drift/significance comparison "
            "(baseline_mean, linear_feature_weighted, lightgbm, catboost)."
        ),
    )
    parser.add_argument(
        "--focal-owner-id",
        type=int,
        default=None,
        help="Authenticated owner context for owner-specific slice metrics and simulation impact.",
    )
    parser.add_argument(
        "--owner-id-col",
        default="owner_id",
        help="Owner column in input CSV used for owner-specific slicing.",
    )
    parser.add_argument(
        "--position-col",
        default="position",
        help="Position column in input CSV used for per-position slice metrics.",
    )
    parser.add_argument("--train-end-season", type=int, required=True, help="Inclusive train end season.")
    parser.add_argument("--val-season", type=int, required=True, help="Validation season year.")
    parser.add_argument("--test-season", type=int, required=True, help="Test season year.")
    parser.add_argument(
        "--simulation-draft-results-csv",
        default="",
        help="Optional draft results CSV for Monte Carlo impact comparison.",
    )
    parser.add_argument(
        "--simulation-players-csv",
        default="",
        help="Optional players CSV for Monte Carlo impact comparison.",
    )
    parser.add_argument(
        "--simulation-budget-csv",
        default="",
        help="Optional draft budget CSV for Monte Carlo impact comparison.",
    )
    parser.add_argument(
        "--simulation-yearly-results-csv",
        default="",
        help="Optional yearly results CSV for Monte Carlo impact comparison.",
    )
    parser.add_argument(
        "--simulation-iterations",
        type=int,
        default=250,
        help="Monte Carlo iterations when simulation impact hook is enabled.",
    )
    parser.add_argument(
        "--simulation-seed",
        type=int,
        default=42,
        help="Monte Carlo seed when simulation impact hook is enabled.",
    )
    parser.add_argument(
        "--simulation-teams-count",
        type=int,
        default=12,
        help="Teams count for simulation impact hook.",
    )
    parser.add_argument(
        "--simulation-roster-size",
        type=int,
        default=16,
        help="Roster size for simulation impact hook.",
    )
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
    # Exclude label/time columns and entity identifiers to avoid memorization leakage.
    excluded = {"season_year", target_col, "id", "owner_id", "player_id", "league_id", "team_id"}
    return sorted(
        [
            col for col in numeric_cols
            if col not in excluded and not col.endswith("_id")
        ]
    )


def _parse_candidates(raw: str) -> list[str]:
    if not raw.strip():
        return []
    return [token.strip().lower() for token in raw.split(",") if token.strip()]


def _build_rankings_from_predictions(
    test_df: pd.DataFrame,
    preds: pd.Series,
    target_season: int,
    position_col: str,
    all_players_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if "player_id" not in test_df.columns:
        raise ValueError("Simulation impact requires 'player_id' in input CSV.")

    aligned = test_df.reset_index(drop=True).copy()
    pred_series = pd.Series(preds).reset_index(drop=True)
    scored = pd.DataFrame(
        {
            "player_id": pd.to_numeric(aligned["player_id"], errors="coerce"),
            "predicted_auction_value": pd.to_numeric(pred_series, errors="coerce"),
        }
    )
    if position_col in aligned.columns:
        scored["position"] = aligned[position_col]
    else:
        scored["position"] = pd.NA
    scored = scored.dropna(subset=["player_id"]).copy()
    scored["player_id"] = scored["player_id"].astype(int)

    grouped = (
        scored.groupby("player_id", as_index=False)
        .agg(
            predicted_auction_value=("predicted_auction_value", "mean"),
            position=("position", "first"),
        )
        .copy()
    )
    grouped["predicted_auction_value"] = grouped["predicted_auction_value"].fillna(1.0).clip(lower=1.0)

    rankings = grouped
    if all_players_df is not None and not all_players_df.empty:
        player_id_col = "player_id" if "player_id" in all_players_df.columns else "Player_ID"
        if player_id_col in all_players_df.columns:
            full_pool = all_players_df[[player_id_col]].copy()
            full_pool = full_pool.rename(columns={player_id_col: "player_id"})
            full_pool["player_id"] = pd.to_numeric(full_pool["player_id"], errors="coerce")
            full_pool = full_pool.dropna(subset=["player_id"]).copy()
            full_pool["player_id"] = full_pool["player_id"].astype(int)
            full_pool = full_pool.drop_duplicates(subset=["player_id"])

            rankings = full_pool.merge(rankings, on="player_id", how="left")

            if "position" not in rankings.columns:
                rankings["position"] = pd.NA

            if "PositionID" in all_players_df.columns:
                pos_lookup = all_players_df[[player_id_col, "PositionID"]].copy()
                pos_lookup = pos_lookup.rename(columns={player_id_col: "player_id", "PositionID": "position_source"})
            elif "position" in all_players_df.columns:
                pos_lookup = all_players_df[[player_id_col, "position"]].copy()
                pos_lookup = pos_lookup.rename(columns={player_id_col: "player_id", "position": "position_source"})
            else:
                pos_lookup = pd.DataFrame(columns=["player_id", "position_source"])

            if not pos_lookup.empty:
                pos_lookup["player_id"] = pd.to_numeric(pos_lookup["player_id"], errors="coerce")
                pos_lookup = pos_lookup.dropna(subset=["player_id"]).copy()
                pos_lookup["player_id"] = pos_lookup["player_id"].astype(int)
                pos_lookup = pos_lookup.drop_duplicates(subset=["player_id"])
                rankings = rankings.merge(pos_lookup, on="player_id", how="left")
                rankings["position"] = rankings["position"].fillna(rankings["position_source"])
                rankings = rankings.drop(columns=["position_source"])

            fallback_value = float(grouped["predicted_auction_value"].median()) if not grouped.empty else 1.0
            rankings["predicted_auction_value"] = rankings["predicted_auction_value"].fillna(fallback_value).clip(lower=1.0)

    rankings["model_score"] = rankings["predicted_auction_value"]
    rankings["season"] = int(target_season)
    rankings["consistency"] = 0.5

    rankings = rankings.sort_values("predicted_auction_value", ascending=False).reset_index(drop=True)
    rankings["rank"] = rankings.index + 1
    return rankings


def _build_simulation_evaluator(args: argparse.Namespace):
    if not args.simulation_draft_results_csv or not args.simulation_players_csv:
        return None

    draft_results_df = pd.read_csv(Path(args.simulation_draft_results_csv))
    players_df = pd.read_csv(Path(args.simulation_players_csv))
    budget_df = pd.read_csv(Path(args.simulation_budget_csv)) if args.simulation_budget_csv else pd.DataFrame()
    yearly_results_df = pd.read_csv(Path(args.simulation_yearly_results_csv)) if args.simulation_yearly_results_csv else pd.DataFrame()

    def _evaluate(test_df: pd.DataFrame, champion_preds: pd.Series, challenger_preds: pd.Series, focal_owner_id: int | None) -> dict[str, object]:
        target_owner_id = int(focal_owner_id or args.focal_owner_id or 1)
        cfg = SimulationConfig(
            iterations=args.simulation_iterations,
            seed=args.simulation_seed,
            target_owner_id=target_owner_id,
            teams_count=args.simulation_teams_count,
            roster_size=args.simulation_roster_size,
            focal_owner_id=target_owner_id,
        )

        champion_rankings = _build_rankings_from_predictions(
            test_df=test_df,
            preds=champion_preds,
            target_season=args.test_season,
            position_col=args.position_col,
            all_players_df=players_df,
        )
        challenger_rankings = _build_rankings_from_predictions(
            test_df=test_df,
            preds=challenger_preds,
            target_season=args.test_season,
            position_col=args.position_col,
            all_players_df=players_df,
        )

        champion_result = run_monte_carlo_draft_simulation(
            draft_results_df=draft_results_df,
            players_df=players_df,
            historical_rankings_df=champion_rankings,
            budget_df=budget_df,
            yearly_results_df=yearly_results_df,
            config=cfg,
        )
        challenger_result = run_monte_carlo_draft_simulation(
            draft_results_df=draft_results_df,
            players_df=players_df,
            historical_rankings_df=challenger_rankings,
            budget_df=budget_df,
            yearly_results_df=yearly_results_df,
            config=cfg,
        )

        champion_summary = champion_result.owner_summary
        challenger_summary = challenger_result.owner_summary
        if champion_summary.empty or challenger_summary.empty:
            return {
                "target_owner_id": target_owner_id,
                "status": "no_owner_summary",
            }

        champion_row = champion_summary.iloc[0]
        challenger_row = challenger_summary.iloc[0]
        champion_points = float(champion_row.get("expected_total_points", 0.0))
        challenger_points = float(challenger_row.get("expected_total_points", 0.0))
        champion_value = float(champion_row.get("expected_value_captured", 0.0))
        challenger_value = float(challenger_row.get("expected_value_captured", 0.0))

        return {
            "target_owner_id": target_owner_id,
            "status": "ok",
            "champion": {
                "expected_total_points": champion_points,
                "expected_value_captured": champion_value,
            },
            "challenger": {
                "expected_total_points": challenger_points,
                "expected_value_captured": challenger_value,
            },
            "delta": {
                "expected_total_points": challenger_points - champion_points,
                "expected_value_captured": challenger_value - champion_value,
            },
        }

    return _evaluate


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_csv)
    df = pd.read_csv(input_path)

    if "season_year" not in df.columns:
        raise ValueError("Input CSV must include season_year column for time-based split.")
    if args.target_col not in df.columns:
        raise ValueError(f"Input CSV missing target column: {args.target_col}")

    feature_cols = _resolve_feature_cols(df, args.target_col, args.feature_cols)
    candidate_models = _parse_candidates(args.candidate_models)
    simulation_evaluator = _build_simulation_evaluator(args)
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
        champion_model=args.champion_model,
        candidate_models=candidate_models,
        focal_owner_id=args.focal_owner_id,
        owner_id_col=args.owner_id_col,
        position_col=args.position_col,
        simulation_evaluator=simulation_evaluator,
    )

    report_path = write_report(report, output_dir=Path(args.output_dir))
    print(f"Model evaluation report written to {report_path}")


if __name__ == "__main__":
    main()
