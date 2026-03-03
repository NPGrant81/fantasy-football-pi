import pandas as pd
import pytest

from etl.load.load_to_postgres import load_normalized_source_to_db


def test_load_normalized_source_to_db_rejects_invalid_dataframe_before_db_write():
    invalid_df = pd.DataFrame(
        [
            {
                "normalized_name": "Josh Allen",
                "position": "QB",
                "team": "BUF",
                # adp missing on purpose
            }
        ]
    )

    with pytest.raises(ValueError) as exc:
        load_normalized_source_to_db(invalid_df, season=2026, source="Yahoo")

    assert "validation failed" in str(exc.value).lower()
