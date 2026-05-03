from __future__ import annotations

import json

import pandas as pd

from etl.modeling.training_pipeline import SplitPolicy, evaluate_candidates, write_report


def _sample_training_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"season_year": 2022, "winning_bid": 20.0, "draft_avg_cost": 18.0, "bargain_score": 0.10},
            {"season_year": 2022, "winning_bid": 26.0, "draft_avg_cost": 22.0, "bargain_score": 0.20},
            {"season_year": 2023, "winning_bid": 31.0, "draft_avg_cost": 28.0, "bargain_score": 0.12},
            {"season_year": 2023, "winning_bid": 35.0, "draft_avg_cost": 30.0, "bargain_score": 0.18},
            {"season_year": 2024, "winning_bid": 40.0, "draft_avg_cost": 35.0, "bargain_score": 0.15},
            {"season_year": 2024, "winning_bid": 44.0, "draft_avg_cost": 38.0, "bargain_score": 0.22},
        ]
    )


def test_evaluate_candidates_returns_expected_shape_and_metrics():
    df = _sample_training_df()
    split = SplitPolicy(train_end_season=2022, val_season=2023, test_season=2024)

    report = evaluate_candidates(
        df=df,
        split=split,
        target_col="winning_bid",
        feature_cols=["draft_avg_cost", "bargain_score"],
    )

    assert report["split"]["train_rows"] == 2
    assert report["split"]["val_rows"] == 2
    assert report["split"]["test_rows"] == 2

    champion = report["champion"]
    challenger = report["challenger"]
    assert champion["name"] == "baseline_mean"
    assert challenger["name"] == "linear_feature_weighted"

    assert champion["regression_metrics"]["mae"] >= 0
    assert challenger["regression_metrics"]["mae"] >= 0
    assert 0 <= champion["ranking_metrics"]["ndcg_at_25"] <= 1
    assert 0 <= challenger["ranking_metrics"]["ndcg_at_25"] <= 1


def test_write_report_persists_json_payload(tmp_path):
    report = {
        "champion": {"name": "baseline_mean"},
        "challenger": {"name": "linear_feature_weighted"},
        "drift_signals": {"mae_pct_delta": 0.01},
    }

    output_path = write_report(report, tmp_path)
    assert output_path.name == "model_eval_report.json"

    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded["champion"]["name"] == "baseline_mean"
    assert loaded["challenger"]["name"] == "linear_feature_weighted"
