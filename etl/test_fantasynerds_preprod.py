import pandas as pd

from etl.extract.extract_fantasynerds import (
    evaluate_fantasynerds_quality,
    fetch_fantasynerds_auction_values,
    transform_fantasynerds_auction_values,
)


class _MockResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_fantasynerds_auction_values_parses_envelope(monkeypatch):
    payload = {
        "DraftRankings": [
            {
                "playerId": "1234",
                "name": "Josh Allen",
                "position": "QB",
                "team": "BUF",
                "auction_value": "30",
                "min_value": "27",
                "max_value": "34",
            }
        ]
    }

    def _mock_get(*args, **kwargs):
        return _MockResponse(payload)

    monkeypatch.setattr("etl.extract.extract_fantasynerds.requests.get", _mock_get)
    df = fetch_fantasynerds_auction_values("fake-key")

    assert len(df) == 1
    assert df.iloc[0]["name"] == "Josh Allen"


def test_transform_fantasynerds_auction_values_maps_expected_fields():
    raw_df = pd.DataFrame(
        [
            {
                "playerId": "1234",
                "name": "Josh Allen",
                "position": "qb",
                "team": "buf",
                "auction_value": "$30",
                "min_value": "27",
                "max_value": "34",
            }
        ]
    )

    normalized_df = transform_fantasynerds_auction_values(raw_df)

    assert len(normalized_df) == 1
    assert normalized_df.iloc[0]["fantasynerds_id"] == "1234"
    assert normalized_df.iloc[0]["normalized_name"] == "josh allen"
    assert normalized_df.iloc[0]["position"] == "QB"
    assert normalized_df.iloc[0]["team"] == "BUF"
    assert normalized_df.iloc[0]["auction_value"] == 30.0
    assert normalized_df.iloc[0]["auction_value_min"] == 27.0
    assert normalized_df.iloc[0]["auction_value_max"] == 34.0


def test_evaluate_fantasynerds_quality_pass_and_fail_paths():
    passing_df = pd.DataFrame(
        [
            {
                "auction_value": 20,
                "auction_value_min": 18,
                "auction_value_max": 23,
            },
            {
                "auction_value": 10,
                "auction_value_min": 8,
                "auction_value_max": 11,
            },
        ]
    )
    pass_report = evaluate_fantasynerds_quality(
        passing_df,
        min_players=2,
        min_auction_coverage=0.5,
        min_minmax_coverage=0.5,
    )
    assert pass_report.passed is True
    assert pass_report.errors == []

    failing_df = pd.DataFrame(
        [
            {
                "auction_value": None,
                "auction_value_min": None,
                "auction_value_max": None,
            }
        ]
    )
    fail_report = evaluate_fantasynerds_quality(
        failing_df,
        min_players=2,
        min_auction_coverage=0.9,
        min_minmax_coverage=0.9,
    )
    assert fail_report.passed is False
    assert len(fail_report.errors) == 3