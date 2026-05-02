"""
Tests for ML feature computation module — Issue #106
====================================================
Covers:
  - compute_player_draft_features
  - compute_owner_season_extensions + compute_keeper_metrics
  - compute_draft_season_features
  - Feature registry schema validation
  - Determinism (golden-dataset / parity)
  - Temporal leakage guard (reference_season)
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest
import yaml

from etl.transform.ml_features import (
    compute_draft_season_features,
    compute_keeper_metrics,
    compute_owner_season_extensions,
    compute_player_draft_features,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

POSITIONS = {"QB": 1, "RB": 2, "WR": 3, "TE": 4, "K": 5}
POS_MAP = {v: k for k, v in POSITIONS.items()}  # {1: "QB", ...}


def _make_draft(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


@pytest.fixture
def simple_draft_df() -> pd.DataFrame:
    """Two seasons, two owners, three positions."""
    return _make_draft([
        # Season 2023 — owner 1
        {"player_id": 101, "owner_id": 1, "season_year": 2023, "position_id": 3, "winning_bid": 50.0, "is_keeper": False},
        {"player_id": 102, "owner_id": 1, "season_year": 2023, "position_id": 2, "winning_bid": 30.0, "is_keeper": False},
        {"player_id": 103, "owner_id": 1, "season_year": 2023, "position_id": 1, "winning_bid": 20.0, "is_keeper": True},
        # Season 2023 — owner 2
        {"player_id": 201, "owner_id": 2, "season_year": 2023, "position_id": 3, "winning_bid": 70.0, "is_keeper": False},
        {"player_id": 202, "owner_id": 2, "season_year": 2023, "position_id": 2, "winning_bid": 25.0, "is_keeper": False},
        {"player_id": 203, "owner_id": 2, "season_year": 2023, "position_id": 1, "winning_bid": 15.0, "is_keeper": False},
        # Season 2024 — owner 1 (player 101 drafted again at higher cost)
        {"player_id": 101, "owner_id": 1, "season_year": 2024, "position_id": 3, "winning_bid": 65.0, "is_keeper": False},
        {"player_id": 104, "owner_id": 1, "season_year": 2024, "position_id": 2, "winning_bid": 10.0, "is_keeper": True},
        # Season 2024 — owner 2
        {"player_id": 201, "owner_id": 2, "season_year": 2024, "position_id": 3, "winning_bid": 80.0, "is_keeper": False},
        {"player_id": 205, "owner_id": 2, "season_year": 2024, "position_id": 1, "winning_bid": 18.0, "is_keeper": False},
    ])


# ---------------------------------------------------------------------------
# compute_player_draft_features
# ---------------------------------------------------------------------------

class TestComputePlayerDraftFeatures:

    def test_returns_one_row_per_player_season(self, simple_draft_df):
        result = compute_player_draft_features(simple_draft_df)
        assert not result.empty
        # Each row in input → one row in output
        assert len(result) == len(simple_draft_df)

    def test_required_columns_present(self, simple_draft_df):
        result = compute_player_draft_features(simple_draft_df)
        for col in ["player_id", "season_year", "draft_avg_cost", "draft_max_cost",
                    "draft_median_cost", "bidding_war_likelihood", "bargain_score",
                    "positional_scarcity_index", "is_keeper"]:
            assert col in result.columns, f"Missing column: {col}"

    def test_draft_avg_cost_single_season(self, simple_draft_df):
        """Player 102 appears only in 2023 — avg, max, median all = 30.0."""
        result = compute_player_draft_features(simple_draft_df)
        row = result[(result["player_id"] == 102) & (result["season_year"] == 2023)].iloc[0]
        assert row["draft_avg_cost"] == pytest.approx(30.0, abs=0.01)
        assert row["draft_max_cost"] == pytest.approx(30.0, abs=0.01)
        assert row["draft_median_cost"] == pytest.approx(30.0, abs=0.01)

    def test_draft_avg_cost_multi_season(self, simple_draft_df):
        """Player 101 was drafted at 50 (2023) and 65 (2024) — avg = 57.5 in 2024 row."""
        result = compute_player_draft_features(simple_draft_df)
        row = result[(result["player_id"] == 101) & (result["season_year"] == 2024)].iloc[0]
        # Both seasons included (no reference_season), avg of [50, 65] = 57.5
        assert row["draft_avg_cost"] == pytest.approx(57.5, abs=0.01)

    def test_reference_season_excludes_future(self, simple_draft_df):
        """With reference_season=2024, player 101's 2024 row should only use 2023 data."""
        result = compute_player_draft_features(simple_draft_df, reference_season=2024)
        row = result[(result["player_id"] == 101) & (result["season_year"] == 2024)].iloc[0]
        # Only 2023 bid (50.0) is before 2024
        assert row["draft_avg_cost"] == pytest.approx(50.0, abs=0.01)

    def test_bidding_war_likelihood_requires_two_seasons(self, simple_draft_df):
        """Player 102 only appears once — CV should be None."""
        result = compute_player_draft_features(simple_draft_df)
        row = result[(result["player_id"] == 102) & (result["season_year"] == 2023)].iloc[0]
        assert row["bidding_war_likelihood"] is None or math.isnan(row["bidding_war_likelihood"] or float("nan"))

    def test_bidding_war_likelihood_nonzero_for_multi_season(self, simple_draft_df):
        """Player 101 drafted at 50 and 65 — CV = stdev/mean > 0."""
        result = compute_player_draft_features(simple_draft_df)
        rows_101 = result[result["player_id"] == 101]
        # At least one row should have a non-None CV
        cv_values = [r for r in rows_101["bidding_war_likelihood"] if r is not None]
        assert len(cv_values) > 0
        assert all(v > 0 for v in cv_values)

    def test_bargain_score_positive_when_below_position_avg(self, simple_draft_df):
        """
        In 2023, WR (pos 3): bids are 50 (p101) and 70 (p201). Avg = 60.
        Player 101 paid 50 < 60 → bargain_score = (60-50)/60 ≈ 0.167 > 0.
        """
        result = compute_player_draft_features(simple_draft_df)
        row = result[(result["player_id"] == 101) & (result["season_year"] == 2023)].iloc[0]
        assert row["bargain_score"] > 0

    def test_bargain_score_negative_when_above_position_avg(self, simple_draft_df):
        """
        In 2023, WR avg = 60. Player 201 paid 70 > 60 → bargain_score < 0.
        """
        result = compute_player_draft_features(simple_draft_df)
        row = result[(result["player_id"] == 201) & (result["season_year"] == 2023)].iloc[0]
        assert row["bargain_score"] < 0

    def test_is_keeper_flag_preserved(self, simple_draft_df):
        """Player 103 has winning_bid=20 but is_keeper=True (set in source data)."""
        result = compute_player_draft_features(simple_draft_df)
        row = result[(result["player_id"] == 103) & (result["season_year"] == 2023)].iloc[0]
        assert row["is_keeper"] == True  # noqa: E712 — np.True_ != True via `is`

    def test_empty_input_returns_empty_df(self):
        empty = pd.DataFrame(columns=["player_id", "season_year", "winning_bid", "is_keeper"])
        result = compute_player_draft_features(empty)
        assert result.empty

    def test_missing_required_column_raises(self):
        bad = pd.DataFrame({"player_id": [1], "season_year": [2023]})
        with pytest.raises(ValueError, match="missing columns"):
            compute_player_draft_features(bad)

    def test_deterministic_on_repeated_calls(self, simple_draft_df):
        """Same input → identical output (no random state)."""
        r1 = compute_player_draft_features(simple_draft_df)
        r2 = compute_player_draft_features(simple_draft_df)
        pd.testing.assert_frame_equal(r1, r2)

    def test_positional_scarcity_between_zero_and_one(self, simple_draft_df):
        """All positional_scarcity_index values must be in (0, 1]."""
        result = compute_player_draft_features(simple_draft_df)
        values = result["positional_scarcity_index"].dropna()
        assert len(values) > 0
        assert (values > 0).all()
        assert (values <= 1.0).all()

    def test_positional_scarcity_consistent_within_position(self, simple_draft_df):
        """All players at the same position in the same season share one scarcity value."""
        result = compute_player_draft_features(simple_draft_df)
        # Player 101 (WR, 2023) and 201 (WR, 2023) should have identical scarcity
        wr_2023 = result[
            (result["season_year"] == 2023) &
            result["player_id"].isin([101, 201])
        ]["positional_scarcity_index"].dropna()
        assert len(wr_2023) == 2
        assert wr_2023.iloc[0] == pytest.approx(wr_2023.iloc[1], abs=0.0001)


# ---------------------------------------------------------------------------
# compute_keeper_metrics
# ---------------------------------------------------------------------------

class TestComputeKeeperMetrics:

    def test_keeper_count_correct(self, simple_draft_df):
        result = compute_keeper_metrics(simple_draft_df)
        # Owner 1, season 2023: player 103 is keeper (bid=20, is_keeper=True)
        row = result[(result["owner_id"] == 1) & (result["season_year"] == 2023)].iloc[0]
        assert row["keeper_count"] == 1
        assert row["keeper_spend"] == pytest.approx(20.0, abs=0.01)

    def test_no_keepers_yields_zero(self, simple_draft_df):
        result = compute_keeper_metrics(simple_draft_df)
        # Owner 2, season 2023: no keepers
        row = result[(result["owner_id"] == 2) & (result["season_year"] == 2023)].iloc[0]
        assert row["keeper_count"] == 0
        assert row["keeper_spend"] == pytest.approx(0.0, abs=0.01)

    def test_empty_input_returns_empty_df(self):
        result = compute_keeper_metrics(pd.DataFrame())
        assert result.empty


# ---------------------------------------------------------------------------
# compute_owner_season_extensions
# ---------------------------------------------------------------------------

class TestComputeOwnerSeasonExtensions:

    def _make_behavior_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {
                "owner_id": 1, "season_year": 2023,
                "total_spend": 110.0, "starting_budget": 200.0,
                "position_spend_pct": {"WR": 0.55, "RB": 0.30, "QB": 0.15},
            },
            {
                "owner_id": 2, "season_year": 2023,
                "total_spend": 180.0, "starting_budget": 200.0,
                "position_spend_pct": {"WR": 0.45, "RB": 0.35, "QB": 0.20},
            },
        ])

    def test_budget_drift_underspend(self):
        df = self._make_behavior_df()
        result = compute_owner_season_extensions(df)
        row = result[result["owner_id"] == 1].iloc[0]
        # (110 - 200) / 200 = -0.45
        assert row["budget_drift"] == pytest.approx(-0.45, abs=0.001)

    def test_budget_drift_closer_to_zero_for_owner_2(self):
        df = self._make_behavior_df()
        result = compute_owner_season_extensions(df)
        row = result[result["owner_id"] == 2].iloc[0]
        # (180 - 200) / 200 = -0.1
        assert row["budget_drift"] == pytest.approx(-0.1, abs=0.001)

    def test_owner_vs_league_avg_sums_near_zero(self):
        """Each position delta (owner - league_avg) should sum to ~0 across all owners."""
        df = self._make_behavior_df()
        result = compute_owner_season_extensions(df)
        for season, grp in result.groupby("season_year"):
            # Sum of position deltas across all owners per position ≈ 0
            pos_sums: dict[str, float] = {}
            for _, row in grp.iterrows():
                delta = row.get("owner_vs_league_avg_spend") or {}
                if isinstance(delta, dict):
                    for pos, v in delta.items():
                        pos_sums[pos] = pos_sums.get(pos, 0.0) + v
            for pos, total in pos_sums.items():
                assert abs(total) < 0.01, f"Position {pos} delta sum = {total}"

    def test_empty_behavior_df_returns_empty(self):
        result = compute_owner_season_extensions(pd.DataFrame())
        assert result.empty


# ---------------------------------------------------------------------------
# compute_draft_season_features
# ---------------------------------------------------------------------------

class TestComputeDraftSeasonFeatures:

    def test_returns_one_row_per_season(self, simple_draft_df):
        result = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        seasons = result["season_year"].tolist()
        assert sorted(seasons) == [2023, 2024]

    def test_total_league_spend_correct(self, simple_draft_df):
        result = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        row_2023 = result[result["season_year"] == 2023].iloc[0]
        # 2023 bids: 50+30+20+70+25+15 = 210
        assert row_2023["total_league_spend"] == pytest.approx(210.0, abs=0.01)

    def test_avg_cost_by_position_present(self, simple_draft_df):
        result = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        row_2023 = result[result["season_year"] == 2023].iloc[0]
        avg = row_2023["avg_cost_by_position"]
        assert isinstance(avg, dict)
        # WR avg in 2023: (50+70)/2 = 60
        assert avg.get("WR") == pytest.approx(60.0, abs=0.01)

    def test_league_avg_position_spend_pct_sums_to_one(self, simple_draft_df):
        result = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        for _, row in result.iterrows():
            pct = row["league_avg_position_spend_pct"]
            if isinstance(pct, dict) and pct:
                total = sum(pct.values())
                assert total == pytest.approx(1.0, abs=0.01), f"Season {row['season_year']}: pct sum = {total}"

    def test_positional_demand_sums_to_one(self, simple_draft_df):
        result = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        for _, row in result.iterrows():
            demand = row["positional_demand"]
            if isinstance(demand, dict) and demand:
                total = sum(demand.values())
                assert total == pytest.approx(1.0, abs=0.01)

    def test_inflation_index_null_for_first_season(self, simple_draft_df):
        result = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        # First season (2023) should have None inflation_index
        first_row = result.sort_values("season_year").iloc[0]
        assert first_row["inflation_index"] is None

    def test_inflation_index_present_for_second_season(self, simple_draft_df):
        result = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        second_row = result.sort_values("season_year").iloc[1]
        infl = second_row["inflation_index"]
        assert isinstance(infl, dict)
        assert "WR" in infl

    def test_inflation_positive_when_prices_rise(self, simple_draft_df):
        """
        WR avg 2023 = 60, WR avg 2024 = (65+80)/2 = 72.5
        Inflation = 72.5/60 - 1 = 0.2083... > 0
        """
        result = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        second_row = result.sort_values("season_year").iloc[1]
        assert second_row["inflation_index"]["WR"] > 0

    def test_gini_between_zero_and_one(self, simple_draft_df):
        result = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        for _, row in result.iterrows():
            g = row["budget_distribution_gini"]
            if g is not None:
                assert 0.0 <= g <= 1.0

    def test_replacement_level_value_is_min_non_keeper(self, simple_draft_df):
        """
        2023 non-keeper WR picks: p101 (50), p201 (70). Min = 50.
        """
        result = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        row_2023 = result[result["season_year"] == 2023].iloc[0]
        repl = row_2023["replacement_level_value"]
        assert repl.get("WR") == pytest.approx(50.0, abs=0.01)

    def test_empty_input_returns_empty_df(self):
        empty = pd.DataFrame(columns=["season_year", "owner_id", "winning_bid", "is_keeper"])
        result = compute_draft_season_features(empty)
        assert result.empty

    def test_missing_required_column_raises(self):
        bad = pd.DataFrame({"season_year": [2023]})
        with pytest.raises(ValueError, match="missing columns"):
            compute_draft_season_features(bad)

    def test_deterministic_on_repeated_calls(self, simple_draft_df):
        r1 = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        r2 = compute_draft_season_features(simple_draft_df, position_abbrev_map=POS_MAP)
        pd.testing.assert_frame_equal(r1, r2)


# ---------------------------------------------------------------------------
# Feature registry schema validation
# ---------------------------------------------------------------------------

REGISTRY_PATH = Path(__file__).parent / "feature_registry.yml"

REQUIRED_KEYS = {
    "name", "level", "formula", "inputs", "output_type",
    "tier", "null_rate_threshold", "offline", "online",
    "temporal_leakage_guard", "owner", "version", "deprecation_policy",
}
VALID_LEVELS = {"player_season", "owner_season", "draft_season"}
VALID_TIERS = {"critical", "standard", "optional"}
VALID_OUTPUT_TYPES = {"float", "int", "bool", "dict", "list[float]"}


class TestFeatureRegistry:

    @pytest.fixture(scope="class")
    def registry(self) -> dict:
        assert REGISTRY_PATH.exists(), f"Registry not found: {REGISTRY_PATH}"
        with open(REGISTRY_PATH) as f:
            return yaml.safe_load(f)

    def test_registry_loads(self, registry):
        assert "features" in registry
        assert isinstance(registry["features"], list)
        assert len(registry["features"]) > 0

    def test_registry_version_present(self, registry):
        assert "version" in registry

    def test_all_required_keys_present(self, registry):
        for feature in registry["features"]:
            missing = REQUIRED_KEYS - set(feature.keys())
            assert not missing, f"Feature '{feature.get('name')}' missing keys: {missing}"

    def test_all_levels_valid(self, registry):
        for feature in registry["features"]:
            assert feature["level"] in VALID_LEVELS, (
                f"Feature '{feature['name']}' has invalid level: {feature['level']}"
            )

    def test_all_tiers_valid(self, registry):
        for feature in registry["features"]:
            assert feature["tier"] in VALID_TIERS, (
                f"Feature '{feature['name']}' has invalid tier: {feature['tier']}"
            )

    def test_all_output_types_valid(self, registry):
        for feature in registry["features"]:
            assert feature["output_type"] in VALID_OUTPUT_TYPES, (
                f"Feature '{feature['name']}' has invalid output_type: {feature['output_type']}"
            )

    def test_null_rate_threshold_in_range(self, registry):
        for feature in registry["features"]:
            thresh = feature["null_rate_threshold"]
            assert 0.0 <= thresh <= 1.0, (
                f"Feature '{feature['name']}' null_rate_threshold out of range: {thresh}"
            )

    def test_critical_features_have_tight_null_threshold(self, registry):
        for feature in registry["features"]:
            if feature["tier"] == "critical":
                assert feature["null_rate_threshold"] <= 0.10, (
                    f"Critical feature '{feature['name']}' null threshold too loose: "
                    f"{feature['null_rate_threshold']}"
                )

    def test_no_duplicate_feature_names(self, registry):
        names = [f["name"] for f in registry["features"]]
        assert len(names) == len(set(names)), "Duplicate feature names found in registry"

    def test_offline_or_online_must_be_true(self, registry):
        for feature in registry["features"]:
            assert feature["offline"] or feature["online"], (
                f"Feature '{feature['name']}' is neither offline nor online — "
                "this feature would be inaccessible"
            )

    def test_inputs_is_list(self, registry):
        for feature in registry["features"]:
            assert isinstance(feature["inputs"], list), (
                f"Feature '{feature['name']}' inputs must be a list"
            )
            assert len(feature["inputs"]) >= 1, (
                f"Feature '{feature['name']}' must have at least one input"
            )
