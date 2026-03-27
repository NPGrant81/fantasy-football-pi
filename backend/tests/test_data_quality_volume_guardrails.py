from statistics import mean, pstdev


def _season_over_season_delta_ratio(previous_count: int, current_count: int) -> float:
    if previous_count <= 0:
        return 0.0
    return abs(current_count - previous_count) / previous_count


def _zscore(value: float, baseline: list[float]) -> float:
    if not baseline:
        return 0.0
    sigma = pstdev(baseline)
    if sigma == 0:
        return 0.0
    return (value - mean(baseline)) / sigma


def _missing_required_datasets(season_counts: dict[str, int], required: dict[str, int]) -> list[str]:
    missing = []
    for dataset_key, min_rows in required.items():
        if int(season_counts.get(dataset_key, 0)) < int(min_rows):
            missing.append(dataset_key)
    return sorted(missing)


def test_volume_guardrail_detects_large_season_over_season_drop():
    previous = 1240
    current = 610

    ratio = _season_over_season_delta_ratio(previous, current)

    # 50.8% drop should trip a 35% safety threshold.
    assert ratio > 0.35


def test_volume_guardrail_detects_large_season_over_season_spike():
    previous = 980
    current = 1680

    ratio = _season_over_season_delta_ratio(previous, current)

    # 71.4% increase should trip a 35% safety threshold.
    assert ratio > 0.35


def test_volume_guardrail_zscore_flags_outlier_dataset_count():
    historical = [995, 1008, 989, 1011, 1002, 997]
    current = 1405

    score = _zscore(current, historical)

    # Beyond 3 sigma is a high-confidence anomaly.
    assert score > 3.0


def test_volume_guardrail_required_dataset_thresholds_detect_missing_rows():
    season_counts = {
        "html_league_awards_normalized": 14,
        "html_league_champions_normalized": 1,
        "html_yearly_leaders_normalized": 0,
    }
    required = {
        "html_league_awards_normalized": 10,
        "html_league_champions_normalized": 1,
        "html_yearly_leaders_normalized": 1,
    }

    missing = _missing_required_datasets(season_counts, required)

    assert missing == ["html_yearly_leaders_normalized"]


def test_volume_guardrail_required_dataset_thresholds_pass_when_healthy():
    season_counts = {
        "html_league_awards_normalized": 14,
        "html_league_champions_normalized": 1,
        "html_yearly_leaders_normalized": 5,
    }
    required = {
        "html_league_awards_normalized": 10,
        "html_league_champions_normalized": 1,
        "html_yearly_leaders_normalized": 1,
    }

    missing = _missing_required_datasets(season_counts, required)

    assert missing == []
