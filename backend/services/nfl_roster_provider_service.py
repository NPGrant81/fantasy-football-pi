from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
import logging
import os
from typing import Any

import pandas as pd
import requests

from backend.services.espn_roster_service import fetch_rosters_for_seasons as fetch_espn_rosters_for_seasons


LOGGER = logging.getLogger(__name__)

_PROVIDER_ESPN = "espn"
_PROVIDER_NFLDB = "nfldb"


def _provider_order(explicit_provider: str | None = None) -> list[str]:
    primary = (explicit_provider or os.getenv("NFL_ROSTER_PROVIDER", _PROVIDER_ESPN)).strip().lower()
    fallback = os.getenv("NFL_ROSTER_PROVIDER_FALLBACK", _PROVIDER_ESPN).strip().lower()

    providers: list[str] = []
    for value in (primary, fallback):
        if value and value not in providers:
            providers.append(value)

    if _PROVIDER_ESPN not in providers:
        providers.append(_PROVIDER_ESPN)

    return providers


def _normalize_nfldb_frame(df: pd.DataFrame, *, season: int) -> pd.DataFrame:
    if df.empty:
        return df

    # Accept a few common schema variants.
    name_col = next(
        (c for c in ["player_name", "full_name", "display_name", "name"] if c in df.columns),
        None,
    )
    team_col = next((c for c in ["team", "team_abbr", "club"] if c in df.columns), None)
    pos_col = next((c for c in ["position", "pos"] if c in df.columns), None)
    id_col = next((c for c in ["player_id", "gsis_id", "id"] if c in df.columns), None)
    status_col = next((c for c in ["status", "roster_status"] if c in df.columns), None)

    if name_col is None or team_col is None or pos_col is None or id_col is None:
        LOGGER.warning(
            "nfl_roster_provider.nfldb_schema_unsupported",
            extra={"columns": list(df.columns)},
        )
        return pd.DataFrame()

    normalized = pd.DataFrame(
        {
            "player_name": df[name_col].astype(str),
            "display_name": df[name_col].astype(str),
            "position": df[pos_col].astype(str).str.upper(),
            "team": df[team_col].astype(str),
            "status": df[status_col].astype(str) if status_col else "Active",
            "player_id": df[id_col].astype(str),
            "gsis_id": df[id_col].astype(str),
            "season": int(season),
        }
    )

    normalized = normalized.replace({"nan": None, "None": None})
    normalized = normalized.dropna(subset=["player_name", "player_id", "team"])  # type: ignore[arg-type]
    return normalized


def _fetch_nfldb_for_season(*, season: int, timeout_seconds: int) -> pd.DataFrame:
    # Expected to be a template URL with {season}, returning CSV or JSON list.
    # Example: https://example.com/nfldb/rosters/{season}.csv
    template = os.getenv("NFLDB_ROSTER_URL_TEMPLATE", "").strip()
    if not template:
        return pd.DataFrame()

    url = template.format(season=season)
    try:
        if url.lower().endswith(".csv"):
            response = requests.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            frame = pd.read_csv(StringIO(response.text))
        else:
            response = requests.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                frame = pd.DataFrame(payload)
            elif isinstance(payload, dict):
                rows = payload.get("items") or payload.get("data") or []
                frame = pd.DataFrame(rows if isinstance(rows, list) else [])
            else:
                frame = pd.DataFrame()
    except Exception as exc:
        LOGGER.warning(
            "nfl_roster_provider.nfldb_fetch_failed",
            extra={"url": url, "season": season, "error": str(exc)},
        )
        return pd.DataFrame()

    return _normalize_nfldb_frame(frame, season=season)


def fetch_current_players(*, provider: str | None = None, timeout_seconds: int = 10) -> pd.DataFrame:
    current_season = datetime.now(timezone.utc).year
    return fetch_rosters_for_seasons(
        [current_season],
        provider=provider,
        timeout_seconds=timeout_seconds,
    )


def fetch_rosters_for_seasons(
    seasons: list[int],
    *,
    provider: str | None = None,
    timeout_seconds: int = 10,
) -> pd.DataFrame:
    normalized_seasons = [int(s) for s in seasons if isinstance(s, int) or str(s).isdigit()]
    if not normalized_seasons:
        normalized_seasons = [datetime.now(timezone.utc).year]

    for candidate in _provider_order(provider):
        if candidate == _PROVIDER_ESPN:
            try:
                frame = fetch_espn_rosters_for_seasons(normalized_seasons, timeout_seconds=timeout_seconds)
                if not frame.empty:
                    LOGGER.info("nfl_roster_provider.using_espn", extra={"rows": len(frame)})
                    return frame
            except Exception as exc:
                LOGGER.warning("nfl_roster_provider.espn_failed", extra={"error": str(exc)})

        elif candidate == _PROVIDER_NFLDB:
            frames: list[pd.DataFrame] = []
            for season in normalized_seasons:
                season_frame = _fetch_nfldb_for_season(season=season, timeout_seconds=timeout_seconds)
                if not season_frame.empty:
                    frames.append(season_frame)
            if frames:
                merged = pd.concat(frames, ignore_index=True)
                LOGGER.info("nfl_roster_provider.using_nfldb", extra={"rows": len(merged)})
                return merged

        else:
            LOGGER.warning("nfl_roster_provider.unknown_provider", extra={"provider": candidate})

    LOGGER.warning("nfl_roster_provider.no_provider_returned_rows")
    return pd.DataFrame()
