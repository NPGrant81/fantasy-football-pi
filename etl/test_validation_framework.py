import pandas as pd

from etl.validation.dataframe_validation import validate_normalized_players_dataframe
from etl.validation.great_expectations_runner import run_normalized_players_expectations


def test_validate_normalized_players_dataframe_valid():
    df = pd.DataFrame(
        [
            {
                "normalized_name": "Josh Allen",
                "position": "QB",
                "team": "BUF",
                "adp": 12.0,
            }
        ]
    )

    report = validate_normalized_players_dataframe(df)
    assert report.valid is True


def test_run_normalized_players_expectations_invalid_missing_column():
    df = pd.DataFrame(
        [
            {
                "normalized_name": "Josh Allen",
                "position": "QB",
                "team": "BUF",
            }
        ]
    )

    report = run_normalized_players_expectations(df)
    assert report.success is False
    assert "adp" in report.details.get("missing_columns", [])
