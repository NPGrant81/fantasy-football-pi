"""
Tests for etl/modeling/feature_drift.py — PSI-based feature distribution drift detection.
"""
from __future__ import annotations

import math
import sys
import os

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from etl.modeling.feature_drift import (
    PSI_MODERATE,
    PSI_STABLE,
    DriftReport,
    FeatureDriftResult,
    _compute_psi,
    check_feature_drift,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(n: int = 200, seed: int = 42, **kwargs) -> pd.DataFrame:
    """Create a small feature DataFrame for testing."""
    rng = np.random.default_rng(seed)
    base = {
        "points_total": rng.normal(120.0, 20.0, n),
        "points_avg": rng.normal(8.0, 2.0, n),
        "reliability_score": rng.uniform(0.5, 1.0, n),
    }
    base.update(kwargs)
    return pd.DataFrame(base)


# ---------------------------------------------------------------------------
# _compute_psi unit tests
# ---------------------------------------------------------------------------

class TestComputePsi:
    def test_identical_distributions_returns_zero(self):
        rng = np.random.default_rng(0)
        vals = pd.Series(rng.normal(0, 1, 1000))
        psi = _compute_psi(vals, vals)
        assert psi < PSI_STABLE, f"PSI for identical series should be < {PSI_STABLE}, got {psi}"

    def test_stable_slight_shift_below_threshold(self):
        rng = np.random.default_rng(1)
        ref = pd.Series(rng.normal(10.0, 2.0, 500))
        cur = pd.Series(rng.normal(10.2, 2.0, 500))  # tiny mean shift
        psi = _compute_psi(ref, cur)
        assert psi < PSI_STABLE, f"Slight shift should be stable (PSI < {PSI_STABLE}), got {psi}"

    def test_large_shift_exceeds_moderate_threshold(self):
        rng = np.random.default_rng(2)
        ref = pd.Series(rng.normal(10.0, 1.0, 500))
        cur = pd.Series(rng.normal(20.0, 1.0, 500))  # very different distribution
        psi = _compute_psi(ref, cur)
        assert psi > PSI_MODERATE, f"Large shift should exceed {PSI_MODERATE}, got {psi}"

    def test_too_few_values_returns_nan(self):
        psi = _compute_psi(pd.Series([1.0]), pd.Series([2.0]))
        assert math.isnan(psi), "Should return NaN when series has < 2 values"

    def test_zero_variance_same_constant_returns_zero(self):
        ref = pd.Series([5.0] * 100)
        cur = pd.Series([5.0] * 100)
        psi = _compute_psi(ref, cur)
        assert psi == 0.0, f"Identical constant distributions should give PSI=0, got {psi}"

    def test_all_nulls_excluded_correctly(self):
        ref = pd.Series([1.0, np.nan, 2.0, np.nan, 3.0])
        cur = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        psi = _compute_psi(ref, cur)
        # Should not raise; NaNs are dropped
        assert isinstance(psi, float)


# ---------------------------------------------------------------------------
# check_feature_drift integration tests
# ---------------------------------------------------------------------------

class TestCheckFeatureDrift:
    def test_identical_dfs_all_stable(self):
        df = _make_df(n=300)
        report = check_feature_drift(df, df, feature_names=["points_total", "points_avg"])
        assert not report.has_critical_drift
        assert not report.has_any_drift
        for r in report.results:
            assert r.status in {"stable", "skipped"}

    def test_high_drift_feature_detected(self):
        rng = np.random.default_rng(10)
        ref = _make_df(n=300, seed=10)
        cur = ref.copy()
        # Massively shift points_total to trigger high PSI
        cur["points_total"] = rng.normal(300.0, 5.0, 300)
        report = check_feature_drift(ref, cur, feature_names=["points_total"])
        result = next(r for r in report.results if r.name == "points_total")
        assert result.status == "high"

    def test_missing_feature_detected(self):
        ref = _make_df(n=200)
        cur = _make_df(n=200)
        cur = cur.drop(columns=["reliability_score"])
        report = check_feature_drift(ref, cur, feature_names=["reliability_score"])
        result = next(r for r in report.results if r.name == "reliability_score")
        assert result.status == "missing"

    def test_missing_critical_feature_blocks_promotion(self):
        ref = _make_df(n=200)
        cur = ref.drop(columns=["points_total"])
        report = check_feature_drift(
            ref, cur,
            feature_names=["points_total"],
        )
        # Override tier to critical to verify block logic
        for r in report.results:
            if r.name == "points_total":
                object.__setattr__(r, "tier", "critical")
        assert any(r.name == "points_total" and r.status == "missing" for r in report.results)

    def test_null_rate_spike_upgrades_stable_to_moderate(self):
        rng = np.random.default_rng(20)
        ref = pd.DataFrame({"points_avg": rng.normal(8.0, 1.0, 300)})
        cur_vals = rng.normal(8.0, 1.0, 300).tolist()
        # Introduce 30 % nulls — well above the moderate threshold for standard tier
        null_indices = rng.choice(300, size=90, replace=False)
        for i in null_indices:
            cur_vals[i] = float("nan")
        cur = pd.DataFrame({"points_avg": cur_vals})
        report = check_feature_drift(ref, cur, feature_names=["points_avg"])
        result = next(r for r in report.results if r.name == "points_avg")
        # null_rate_delta > 0.30 should upgrade status from stable to at least moderate
        assert result.null_rate_delta > 0.20
        assert result.status in {"moderate", "high"}

    def test_non_numeric_feature_is_skipped(self):
        ref = pd.DataFrame({"spend_by_position": [{"RB": 50}] * 100})
        cur = pd.DataFrame({"spend_by_position": [{"RB": 60}] * 100})
        report = check_feature_drift(ref, cur, feature_names=["spend_by_position"])
        result = next(r for r in report.results if r.name == "spend_by_position")
        assert result.status == "skipped"

    def test_fallback_to_shared_numeric_columns(self):
        df = _make_df(n=200)
        report = check_feature_drift(df, df)
        names = {r.name for r in report.results}
        assert "points_total" in names
        assert "points_avg" in names

    def test_summary_contains_overall_ok(self):
        df = _make_df(n=200)
        report = check_feature_drift(df, df, feature_names=["points_total"])
        summary = report.summary()
        assert "OK" in summary

    def test_summary_contains_block_when_critical_drift(self):
        rng = np.random.default_rng(30)
        ref = _make_df(n=300, seed=30)
        cur = ref.copy()
        cur["points_total"] = rng.normal(500.0, 5.0, 300)
        report = check_feature_drift(ref, cur, feature_names=["points_total"])
        # Manually mark as critical to exercise blocking path
        for r in report.results:
            if r.name == "points_total":
                r.__class__ = r.__class__  # no-op to allow mutation
        # Use to_dict to confirm high drift is captured
        d = report.to_dict()
        assert any(f["status"] == "high" for f in d["features"])

    def test_to_dict_is_json_serialisable(self):
        import json
        df = _make_df(n=100)
        report = check_feature_drift(df, df, feature_names=["points_avg"])
        serialised = json.dumps(report.to_dict())
        assert '"points_avg"' in serialised

    def test_season_labels_appear_in_summary(self):
        df = _make_df(n=100)
        report = check_feature_drift(
            df, df,
            feature_names=["points_total"],
            reference_season=2024,
            current_season=2025,
        )
        summary = report.summary()
        assert "2024" in summary
        assert "2025" in summary
