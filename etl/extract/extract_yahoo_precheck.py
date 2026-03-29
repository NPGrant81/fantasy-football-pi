"""Yahoo pre-production quality checks.

These checks are read-only and intended to gate ingestion when Yahoo auth/data
quality is degraded.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class YahooQualityReport:
    total_rows: int
    adp_rows: int
    adp_coverage: float
    passed: bool
    errors: list[str]


def evaluate_yahoo_quality(
    normalized_df: pd.DataFrame,
    *,
    min_players: int = 50,
    min_adp_coverage: float = 0.80,
) -> YahooQualityReport:
    total_rows = len(normalized_df)
    if total_rows == 0:
        return YahooQualityReport(
            total_rows=0,
            adp_rows=0,
            adp_coverage=0.0,
            passed=False,
            errors=["No rows returned from Yahoo."],
        )

    adp_mask = pd.to_numeric(normalized_df.get("adp"), errors="coerce").fillna(0) > 0
    adp_rows = int(adp_mask.sum())
    adp_coverage = adp_rows / total_rows

    errors: list[str] = []
    if total_rows < min_players:
        errors.append(f"Expected at least {min_players} rows, got {total_rows}.")
    if adp_coverage < min_adp_coverage:
        errors.append(
            f"ADP coverage below threshold: {adp_coverage:.1%} < {min_adp_coverage:.1%}."
        )

    return YahooQualityReport(
        total_rows=total_rows,
        adp_rows=adp_rows,
        adp_coverage=adp_coverage,
        passed=not errors,
        errors=errors,
    )