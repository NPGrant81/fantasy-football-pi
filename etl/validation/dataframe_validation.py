from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class DataFrameValidationReport:
    valid: bool
    engine: str
    errors: list[str] = field(default_factory=list)


REQUIRED_COLUMNS = ["normalized_name", "position", "team", "adp"]


def _manual_validate_dataframe(df: pd.DataFrame) -> DataFrameValidationReport:
    errors: list[str] = []
    for column in REQUIRED_COLUMNS:
        if column not in df.columns:
            errors.append(f"missing column: {column}")

    if "normalized_name" in df.columns and df["normalized_name"].isna().any():
        errors.append("normalized_name contains null values")

    if "position" in df.columns and df["position"].isna().any():
        errors.append("position contains null values")

    if "adp" in df.columns:
        bad_adp = pd.to_numeric(df["adp"], errors="coerce").isna().sum()
        if bad_adp > 0:
            errors.append("adp contains non-numeric values")

    return DataFrameValidationReport(valid=not errors, engine="manual", errors=errors)


def validate_normalized_players_dataframe(df: pd.DataFrame) -> DataFrameValidationReport:
    try:
        import pandera as pa  # type: ignore
        from pandera import Column, DataFrameSchema, Check  # type: ignore
    except Exception:
        return _manual_validate_dataframe(df)

    schema = DataFrameSchema(
        {
            "normalized_name": Column(str, nullable=False),
            "position": Column(str, nullable=False),
            "team": Column(str, nullable=True),
            "adp": Column(float, checks=Check.ge(0), nullable=False, coerce=True),
        },
        coerce=True,
    )

    try:
        schema.validate(df, lazy=True)
        return DataFrameValidationReport(valid=True, engine="pandera")
    except Exception as exc:
        return DataFrameValidationReport(
            valid=False,
            engine="pandera",
            errors=[str(exc)],
        )
