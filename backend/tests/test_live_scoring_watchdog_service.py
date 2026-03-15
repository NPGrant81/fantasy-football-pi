from backend.services.live_scoring_watchdog_service import WatchdogThresholds, evaluate_watchdog_alerts


def test_evaluate_watchdog_alerts_no_runs_no_alerts():
    alerts = evaluate_watchdog_alerts(
        {
            "runs_considered": 0,
            "failure_rate": 0.0,
            "degraded_runs": 0,
            "top_error_signatures": [],
        },
        thresholds=WatchdogThresholds(),
    )
    assert alerts == []


def test_evaluate_watchdog_alerts_emits_threshold_breaches():
    alerts = evaluate_watchdog_alerts(
        {
            "runs_considered": 20,
            "failure_rate": 0.55,
            "degraded_runs": 6,
            "top_error_signatures": [
                {"error_signature": "IngestFetchError", "count": 4}
            ],
        },
        thresholds=WatchdogThresholds(
            failure_rate=0.5,
            degraded_runs=5,
            repeated_error_count=3,
            limit=20,
        ),
    )
    assert len(alerts) == 3
    assert {item["alert_type"] for item in alerts} == {
        "failure_rate",
        "degraded_runs",
        "repeated_error_signature",
    }
