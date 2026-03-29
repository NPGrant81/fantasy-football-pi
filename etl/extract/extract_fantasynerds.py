"""FantasyNerds auction value extractor and normalization helpers.

This module is intentionally DB-agnostic so it can be used for pre-prod
connectivity and payload quality checks before any production ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

from etl.transform.normalize import normalize_player_name

FANTASYNERDS_AUCTION_URL = "https://api.fantasynerds.com/v1/nfl/auction/"


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fetch_fantasynerds_auction_values(
    api_key: str,
    *,
    teams: int = 12,
    budget: int = 200,
    scoring_format: str = "ppr",
    timeout: int = 30,
) -> pd.DataFrame:
    """Fetch raw FantasyNerds auction rankings as a DataFrame.

    Expected response envelope:
    {
      "DraftRankings": [...]
    }
    """
    if not api_key or not str(api_key).strip():
        raise ValueError("FantasyNerds API key is required.")

    params = {
        "apikey": api_key,
        "teams": teams,
        "budget": budget,
        "format": scoring_format,
    }
    response = requests.get(FANTASYNERDS_AUCTION_URL, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    rows = payload.get("DraftRankings") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return pd.DataFrame()

    return pd.DataFrame(rows)


def transform_fantasynerds_auction_values(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize FantasyNerds auction response into ETL standard columns."""
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "fantasynerds_id",
                "normalized_name",
                "position",
                "team",
                "adp",
                "auction_value",
                "auction_value_min",
                "auction_value_max",
            ]
        )

    normalized_rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        raw_name = row.get("name") or row.get("player_name") or ""
        raw_position = row.get("position") or row.get("pos") or ""
        raw_team = row.get("team") or row.get("nfl_team") or ""

        normalized_rows.append(
            {
                "fantasynerds_id": str(row.get("playerId") or row.get("player_id") or "").strip() or None,
                "normalized_name": normalize_player_name(str(raw_name)),
                "position": str(raw_position).strip().upper(),
                "team": str(raw_team).strip().upper(),
                "adp": _parse_float(row.get("adp")) or 0.0,
                "auction_value": _parse_float(row.get("auction_value")),
                "auction_value_min": _parse_float(row.get("min_value")),
                "auction_value_max": _parse_float(row.get("max_value")),
            }
        )

    result = pd.DataFrame(normalized_rows)
    result["adp"] = pd.to_numeric(result["adp"], errors="coerce").fillna(0.0)
    return result


@dataclass
class FantasyNerdsQualityReport:
    total_rows: int
    auction_value_rows: int
    minmax_rows: int
    auction_coverage: float
    minmax_coverage: float
    passed: bool
    errors: list[str]


def evaluate_fantasynerds_quality(
    normalized_df: pd.DataFrame,
    *,
    min_players: int = 150,
    min_auction_coverage: float = 0.80,
    min_minmax_coverage: float = 0.50,
) -> FantasyNerdsQualityReport:
    """Compute pass/fail quality checks for a pre-production ingestion gate."""
    total_rows = len(normalized_df)
    if total_rows == 0:
        return FantasyNerdsQualityReport(
            total_rows=0,
            auction_value_rows=0,
            minmax_rows=0,
            auction_coverage=0.0,
            minmax_coverage=0.0,
            passed=False,
            errors=["No rows returned from FantasyNerds."],
        )

    auction_mask = pd.to_numeric(normalized_df.get("auction_value"), errors="coerce").fillna(0) > 0
    min_mask = pd.to_numeric(normalized_df.get("auction_value_min"), errors="coerce").notna()
    max_mask = pd.to_numeric(normalized_df.get("auction_value_max"), errors="coerce").notna()

    auction_value_rows = int(auction_mask.sum())
    minmax_rows = int((min_mask & max_mask).sum())
    auction_coverage = auction_value_rows / total_rows
    minmax_coverage = minmax_rows / total_rows

    errors: list[str] = []
    if total_rows < min_players:
        errors.append(
            f"Expected at least {min_players} rows, got {total_rows}."
        )
    if auction_coverage < min_auction_coverage:
        errors.append(
            "Auction value coverage below threshold: "
            f"{auction_coverage:.1%} < {min_auction_coverage:.1%}."
        )
    if minmax_coverage < min_minmax_coverage:
        errors.append(
            "Min/Max coverage below threshold: "
            f"{minmax_coverage:.1%} < {min_minmax_coverage:.1%}."
        )

    return FantasyNerdsQualityReport(
        total_rows=total_rows,
        auction_value_rows=auction_value_rows,
        minmax_rows=minmax_rows,
        auction_coverage=auction_coverage,
        minmax_coverage=minmax_coverage,
        passed=not errors,
        errors=errors,
    )