from __future__ import annotations

import argparse
import json
from pathlib import Path

from etl.transform.monte_carlo_simulation import (
    SimulationConfig,
    run_monte_carlo_from_paths,
    summarize_team_distribution,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full-league Monte Carlo auction draft simulations and export metrics."
    )
    parser.add_argument("--iterations", type=int, default=1000, help="Number of simulated full drafts.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument("--target-owner-id", type=int, default=1, help="Owner ID for focused summary metrics.")
    parser.add_argument("--teams-count", type=int, default=12, help="Number of teams in the league simulation.")
    parser.add_argument("--roster-size", type=int, default=16, help="Roster size per team.")
    parser.add_argument(
        "--draft-results",
        default="backend/data/draft_results.csv",
        help="Path to cleaned historical draft results CSV.",
    )
    parser.add_argument(
        "--players",
        default="backend/data/players.csv",
        help="Path to players CSV.",
    )
    parser.add_argument(
        "--historical-rankings",
        default="backend/data/historical_rankings.csv",
        help="Path to historical rankings/features CSV.",
    )
    parser.add_argument(
        "--draft-budget",
        default="backend/data/draft_budget.csv",
        help="Path to draft budget CSV.",
    )
    parser.add_argument(
        "--yearly-results",
        default="",
        help="Optional path to yearly results CSV (for projected points input).",
    )
    parser.add_argument(
        "--output-dir",
        default="backend/data/simulation",
        help="Output directory for simulation artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = SimulationConfig(
        iterations=args.iterations,
        seed=args.seed,
        target_owner_id=args.target_owner_id,
        teams_count=args.teams_count,
        roster_size=args.roster_size,
    )

    result = run_monte_carlo_from_paths(
        draft_results_path=args.draft_results,
        players_path=args.players,
        historical_rankings_path=args.historical_rankings,
        draft_budget_path=args.draft_budget,
        yearly_results_path=args.yearly_results or None,
        config=config,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    picks_path = output_dir / "draft_picks.csv"
    team_metrics_path = output_dir / "team_metrics.csv"
    owner_summary_path = output_dir / "owner_summary.csv"
    assumptions_path = output_dir / "assumptions.json"
    owner_distribution_path = output_dir / "owner_points_distribution.json"

    result.draft_picks.to_csv(picks_path, index=False)
    result.team_metrics.to_csv(team_metrics_path, index=False)
    result.owner_summary.to_csv(owner_summary_path, index=False)

    with assumptions_path.open("w", encoding="utf-8") as handle:
        json.dump(result.assumptions, handle, indent=2)

    owner_distribution = summarize_team_distribution(
        result.team_metrics,
        owner_id=config.target_owner_id,
    )
    with owner_distribution_path.open("w", encoding="utf-8") as handle:
        json.dump(owner_distribution, handle, indent=2)

    print(
        "Monte Carlo simulation complete. "
        f"Iterations={config.iterations}, Teams={config.teams_count}, RosterSize={config.roster_size}."
    )
    print(f"Draft picks: {picks_path}")
    print(f"Team metrics: {team_metrics_path}")
    print(f"Owner summary: {owner_summary_path}")
    print(f"Assumptions: {assumptions_path}")
    print(f"Owner point distribution: {owner_distribution_path}")


if __name__ == "__main__":
    main()