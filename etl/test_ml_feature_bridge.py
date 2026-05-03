"""Tests for ml_feature_bridge — Issue #107 integration layer.

Covers:
  - build_simulation_rankings basic conversion
  - predicted_auction_value from draft_avg_cost
  - model_score from bargain_score
  - consistency from bidding_war_likelihood (CV)
  - inflation adjustment via draft_season_features
  - target_season temporal guard
  - most-recent-season selection per player
  - missing required columns raises ValueError
  - empty input returns empty DataFrame
  - end-to-end bridge → simulation integration
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd
import pytest

from etl.transform.ml_feature_bridge import (
    _cv_to_consistency,
    _extract_inflation_map,
    build_simulation_rankings,
)
from etl.transform.monte_carlo_simulation import (
    SimulationConfig,
    run_monte_carlo_draft_simulation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_player_features(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


@pytest.fixture
def simple_player_features() -> pd.DataFrame:
    """Three players, two seasons each."""
    return _make_player_features([
        # Player 101 — consistent, bargain pick
        {"player_id": 101, "season_year": 2023, "draft_avg_cost": 40.0, "bargain_score": 0.20, "bidding_war_likelihood": 0.10},
        {"player_id": 101, "season_year": 2024, "draft_avg_cost": 48.0, "bargain_score": 0.15, "bidding_war_likelihood": 0.12},
        # Player 102 — volatile, overpaid
        {"player_id": 102, "season_year": 2023, "draft_avg_cost": 25.0, "bargain_score": -0.10, "bidding_war_likelihood": 0.80},
        {"player_id": 102, "season_year": 2024, "draft_avg_cost": 30.0, "bargain_score": -0.05, "bidding_war_likelihood": 0.75},
        # Player 103 — unknown history (None values)
        {"player_id": 103, "season_year": 2023, "draft_avg_cost": None, "bargain_score": None, "bidding_war_likelihood": None},
    ])


@pytest.fixture
def simple_draft_season_features() -> pd.DataFrame:
    """Two seasons of season-level features with inflation index."""
    return pd.DataFrame([
        {
            "season_year": 2023,
            "inflation_index": None,  # first season — no prior
        },
        {
            "season_year": 2024,
            "inflation_index": {"QB": 0.05, "RB": 0.10, "WR": 0.08},  # ~7.67% avg
        },
    ])


# ---------------------------------------------------------------------------
# Unit tests — _cv_to_consistency
# ---------------------------------------------------------------------------

class TestCvToConsistency:

    def test_zero_cv_yields_perfect_consistency(self):
        assert _cv_to_consistency(0.0) == pytest.approx(1.0, abs=1e-6)

    def test_cv_one_yields_zero_consistency(self):
        assert _cv_to_consistency(1.0) == pytest.approx(0.0, abs=1e-6)

    def test_cv_above_one_is_clipped_to_zero(self):
        assert _cv_to_consistency(2.5) == pytest.approx(0.0, abs=1e-6)

    def test_none_yields_neutral_consistency(self):
        assert _cv_to_consistency(None) == pytest.approx(0.5, abs=1e-6)

    def test_nan_yields_neutral_consistency(self):
        assert _cv_to_consistency(float("nan")) == pytest.approx(0.5, abs=1e-6)

    def test_mid_cv_linearly_maps(self):
        # CV = 0.4 → consistency = 0.6
        assert _cv_to_consistency(0.4) == pytest.approx(0.6, abs=1e-6)


# ---------------------------------------------------------------------------
# Unit tests — _extract_inflation_map
# ---------------------------------------------------------------------------

class TestExtractInflationMap:

    def test_returns_empty_when_no_features(self):
        result = _extract_inflation_map(None, target_season=2025)
        assert result == {}

    def test_returns_empty_when_no_target_season(self, simple_draft_season_features):
        result = _extract_inflation_map(simple_draft_season_features, target_season=None)
        assert result == {}

    def test_picks_latest_prior_season(self, simple_draft_season_features):
        result = _extract_inflation_map(simple_draft_season_features, target_season=2025)
        # Only 2024 row has inflation_index (2023 is None)
        assert "WR" in result
        assert result["WR"] == pytest.approx(0.08, abs=1e-6)

    def test_ignores_target_season_itself(self, simple_draft_season_features):
        # target_season=2024 should only use 2023 (None → empty map)
        result = _extract_inflation_map(simple_draft_season_features, target_season=2024)
        assert result == {}

    def test_returns_empty_when_inflation_column_missing(self):
        df = pd.DataFrame([{"season_year": 2024, "total_league_spend": 500.0}])
        result = _extract_inflation_map(df, target_season=2025)
        assert result == {}


# ---------------------------------------------------------------------------
# Unit tests — build_simulation_rankings
# ---------------------------------------------------------------------------

class TestBuildSimulationRankings:

    def test_required_columns_present_in_output(self, simple_player_features):
        result = build_simulation_rankings(simple_player_features, target_season=2025)
        for col in ["player_id", "predicted_auction_value", "model_score", "consistency", "season"]:
            assert col in result.columns, f"Missing column: {col}"

    def test_one_row_per_player(self, simple_player_features):
        result = build_simulation_rankings(simple_player_features, target_season=2025)
        assert len(result) == result["player_id"].nunique()

    def test_uses_most_recent_prior_season(self, simple_player_features):
        """Player 101 has 2023 (avg=40) and 2024 (avg=48) — should use 2024 row."""
        result = build_simulation_rankings(simple_player_features, target_season=2025)
        row = result[result["player_id"] == 101].iloc[0]
        # Most recent prior season is 2024 with draft_avg_cost=48
        assert row["predicted_auction_value"] == pytest.approx(48.0, abs=0.01)
        assert row["season"] == 2024

    def test_target_season_excludes_current_season(self, simple_player_features):
        """With target_season=2024, player 101 should use 2023 row (avg=40)."""
        result = build_simulation_rankings(simple_player_features, target_season=2024)
        row = result[result["player_id"] == 101].iloc[0]
        assert row["predicted_auction_value"] == pytest.approx(40.0, abs=0.01)
        assert row["season"] == 2023

    def test_predicted_auction_value_floored_at_one(self, simple_player_features):
        """Player 103 has None draft_avg_cost — should floor to 1.0."""
        result = build_simulation_rankings(simple_player_features, target_season=2025)
        row = result[result["player_id"] == 103].iloc[0]
        assert row["predicted_auction_value"] >= 1.0

    def test_model_score_positive_for_bargain_player(self, simple_player_features):
        """Player 101 has positive bargain_score — model_score should be > 0."""
        result = build_simulation_rankings(simple_player_features, target_season=2025)
        row = result[result["player_id"] == 101].iloc[0]
        assert row["model_score"] > 0.0

    def test_model_score_zero_for_overpaid_player(self, simple_player_features):
        """Player 102 has negative bargain_score — model_score should be 0 (clamped)."""
        result = build_simulation_rankings(simple_player_features, target_season=2025)
        row = result[result["player_id"] == 102].iloc[0]
        assert row["model_score"] == pytest.approx(0.0, abs=1e-6)

    def test_high_cv_yields_low_consistency(self, simple_player_features):
        """Player 102 has CV ~0.75 — consistency should be ~0.25."""
        result = build_simulation_rankings(simple_player_features, target_season=2025)
        row = result[result["player_id"] == 102].iloc[0]
        assert row["consistency"] < 0.5

    def test_low_cv_yields_high_consistency(self, simple_player_features):
        """Player 101 has CV ~0.12 — consistency should be ~0.88."""
        result = build_simulation_rankings(simple_player_features, target_season=2025)
        row = result[result["player_id"] == 101].iloc[0]
        assert row["consistency"] > 0.7

    def test_unknown_history_yields_neutral_consistency(self, simple_player_features):
        """Player 103 has None CV — should yield 0.5 neutral consistency."""
        result = build_simulation_rankings(simple_player_features, target_season=2025)
        row = result[result["player_id"] == 103].iloc[0]
        assert row["consistency"] == pytest.approx(0.5, abs=1e-6)

    def test_inflation_raises_predicted_value(self, simple_player_features, simple_draft_season_features):
        """Inflation ~7.67% should raise player 101's value from 48 to ~51.7."""
        without = build_simulation_rankings(simple_player_features, target_season=2025)
        with_infl = build_simulation_rankings(
            simple_player_features,
            draft_season_features=simple_draft_season_features,
            target_season=2025,
        )
        val_without = without[without["player_id"] == 101].iloc[0]["predicted_auction_value"]
        val_with = with_infl[with_infl["player_id"] == 101].iloc[0]["predicted_auction_value"]
        assert val_with > val_without

    def test_empty_input_returns_empty_df(self):
        cols = ["player_id", "season_year", "draft_avg_cost", "bargain_score", "bidding_war_likelihood"]
        result = build_simulation_rankings(pd.DataFrame(columns=cols))
        assert result.empty

    def test_missing_required_column_raises(self):
        bad = pd.DataFrame({"player_id": [1], "season_year": [2024], "draft_avg_cost": [10.0]})
        with pytest.raises(ValueError, match="missing columns"):
            build_simulation_rankings(bad)

    def test_output_all_values_above_minimum_floor(self, simple_player_features):
        result = build_simulation_rankings(simple_player_features, target_season=2025)
        assert (result["predicted_auction_value"] >= 1.0).all()
        assert (result["model_score"] >= 0.0).all()
        assert (result["consistency"] >= 0.0).all()
        assert (result["consistency"] <= 1.0).all()


# ---------------------------------------------------------------------------
# Integration test — bridge → simulation end-to-end
# ---------------------------------------------------------------------------

def _make_simulation_players() -> pd.DataFrame:
    positions = [8002, 8003, 8004, 8005, 8006, 8099]
    return pd.DataFrame([
        {
            "Player_ID": 100 + i,
            "PlayerName": f"Player {100 + i}",
            "PositionID": positions[(i - 1) % len(positions)],
        }
        for i in range(1, 73)
    ])


def _make_simulation_budgets() -> pd.DataFrame:
    return pd.DataFrame([{"OwnerID": oid, "DraftBudget": "$200"} for oid in range(1, 5)])


def _make_simulation_draft_results() -> pd.DataFrame:
    # Use the upstream column names that run_monte_carlo_draft_simulation normalises.
    # 'Year' → 'year', 'OwnerID' → 'owner_id', 'PlayerID' → 'player_id',
    # 'PositionID' → 'position_id', 'WinningBid' → 'winning_bid'.
    return pd.DataFrame([
        {"PlayerID": 101, "OwnerID": 1, "Year": 2023, "WinningBid": 45.0, "PositionID": 8003},
        {"PlayerID": 102, "OwnerID": 2, "Year": 2023, "WinningBid": 30.0, "PositionID": 8004},
        {"PlayerID": 101, "OwnerID": 1, "Year": 2024, "WinningBid": 55.0, "PositionID": 8003},
        {"PlayerID": 102, "OwnerID": 2, "Year": 2024, "WinningBid": 28.0, "PositionID": 8004},
    ])


class TestBridgeToSimulationIntegration:

    def test_bridge_rankings_accepted_by_simulation_engine(self, simple_player_features):
        """build_simulation_rankings output can be passed directly to run_monte_carlo_draft_simulation."""
        rankings = build_simulation_rankings(simple_player_features, target_season=2025)
        players = _make_simulation_players()
        budgets = _make_simulation_budgets()
        draft_df = _make_simulation_draft_results()

        config = SimulationConfig(
            iterations=3,
            seed=42,
            teams_count=4,
            roster_size=8,
            target_owner_id=1,
            position_limits={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DEF": 1, "K": 1},
        )

        result = run_monte_carlo_draft_simulation(
            draft_results_df=draft_df,
            players_df=players,
            historical_rankings_df=rankings,
            budget_df=budgets,
            yearly_results_df=pd.DataFrame(),
            config=config,
        )

        assert not result.draft_picks.empty
        assert not result.team_metrics.empty
        # Budget constraints respected
        by_owner = result.team_metrics.groupby(["iteration", "owner_id"], as_index=False).first()
        assert (by_owner["budget_remaining"] >= 0).all()

    def test_simulation_with_bridge_produces_valid_pick_columns(self, simple_player_features):
        """Simulation output contains expected columns when bridge rankings are used."""
        rankings = build_simulation_rankings(simple_player_features, target_season=2025)
        players = _make_simulation_players()
        budgets = _make_simulation_budgets()
        draft_df = _make_simulation_draft_results()

        config = SimulationConfig(iterations=2, seed=7, teams_count=4, roster_size=8, target_owner_id=1)

        result = run_monte_carlo_draft_simulation(
            draft_results_df=draft_df,
            players_df=players,
            historical_rankings_df=rankings,
            budget_df=budgets,
            yearly_results_df=pd.DataFrame(),
            config=config,
        )

        for col in ["iteration", "player_id", "owner_id", "winning_bid", "predicted_auction_value"]:
            assert col in result.draft_picks.columns, f"Missing column: {col}"

    def test_no_duplicate_players_per_iteration_with_bridge(self, simple_player_features):
        """Each player appears at most once per iteration when bridge is used."""
        rankings = build_simulation_rankings(simple_player_features, target_season=2025)
        players = _make_simulation_players()
        budgets = _make_simulation_budgets()
        draft_df = _make_simulation_draft_results()

        config = SimulationConfig(iterations=5, seed=123, teams_count=4, roster_size=8, target_owner_id=1)

        result = run_monte_carlo_draft_simulation(
            draft_results_df=draft_df,
            players_df=players,
            historical_rankings_df=rankings,
            budget_df=budgets,
            yearly_results_df=pd.DataFrame(),
            config=config,
        )

        dups = result.draft_picks.groupby(["iteration", "player_id"]).size()
        assert dups.max() == 1, "Duplicate player assigned within a single iteration"
