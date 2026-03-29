import pandas as pd

from etl.extract.extract_yahoo_precheck import evaluate_yahoo_quality


def test_evaluate_yahoo_quality_passes_with_thresholds_met():
    df = pd.DataFrame(
        [
            {"adp": 1},
            {"adp": 2},
            {"adp": 3},
        ]
    )
    report = evaluate_yahoo_quality(df, min_players=3, min_adp_coverage=0.9)
    assert report.passed is True
    assert report.errors == []


def test_evaluate_yahoo_quality_fails_on_low_volume_and_coverage():
    df = pd.DataFrame(
        [
            {"adp": 0},
        ]
    )
    report = evaluate_yahoo_quality(df, min_players=2, min_adp_coverage=0.8)
    assert report.passed is False
    assert len(report.errors) == 2