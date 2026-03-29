from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

import pandas as pd
import requests


LOGGER = logging.getLogger(__name__)

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams?limit=40"
ESPN_TEAM_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster"


def _safe_get_json(url: str, *, timeout_seconds: int = 10) -> dict[str, Any] | None:
    try:
        response = requests.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload
    except Exception as exc:
        LOGGER.warning(
            "espn_roster.fetch_failed",
            extra={"url": url, "error": str(exc)},
        )
    return None


def _extract_team_index(payload: dict[str, Any]) -> list[dict[str, str]]:
    teams: list[dict[str, str]] = []
    for sport in payload.get("sports", []) or []:
        for league in sport.get("leagues", []) or []:
            for wrapped in league.get("teams", []) or []:
                team = wrapped.get("team") if isinstance(wrapped, dict) else None
                if not isinstance(team, dict):
                    continue
                team_id = str(team.get("id") or "").strip()
                abbr = str(team.get("abbreviation") or "").strip()
                if not team_id or not abbr:
                    continue
                teams.append({"id": team_id, "abbr": abbr})
    return teams


def _extract_athletes(roster_payload: dict[str, Any]) -> list[dict[str, Any]]:
    athletes: list[dict[str, Any]] = []

    direct = roster_payload.get("athletes")
    if isinstance(direct, list):
        for group in direct:
            if isinstance(group, dict) and isinstance(group.get("items"), list):
                for athlete in group.get("items") or []:
                    if isinstance(athlete, dict):
                        athletes.append(athlete)
            elif isinstance(group, dict):
                athletes.append(group)

    flat = roster_payload.get("team", {}).get("athletes")
    if isinstance(flat, list):
        for athlete in flat:
            if isinstance(athlete, dict):
                athletes.append(athlete)

    return athletes


def _status_from_athlete(athlete: dict[str, Any]) -> str:
    if athlete.get("active") is True:
        return "Active"
    injury_status = athlete.get("injuries")
    if isinstance(injury_status, list) and injury_status:
        return "Injured"
    return "Inactive"


def fetch_current_players(*, timeout_seconds: int = 10) -> pd.DataFrame:
    teams_payload = _safe_get_json(ESPN_TEAMS_URL, timeout_seconds=timeout_seconds)
    if not teams_payload:
        return pd.DataFrame()

    teams = _extract_team_index(teams_payload)
    if not teams:
        return pd.DataFrame()

    current_season = datetime.now(timezone.utc).year
    rows: list[dict[str, Any]] = []

    for team in teams:
        roster_url = ESPN_TEAM_ROSTER_URL.format(team_id=team["id"])
        roster_payload = _safe_get_json(roster_url, timeout_seconds=timeout_seconds)
        if not roster_payload:
            continue

        athletes = _extract_athletes(roster_payload)
        for athlete in athletes:
            player_id = str(athlete.get("id") or "").strip()
            full_name = str(athlete.get("fullName") or athlete.get("displayName") or "").strip()
            if not player_id or not full_name:
                continue

            position = ""
            pos_info = athlete.get("position")
            if isinstance(pos_info, dict):
                position = str(pos_info.get("abbreviation") or pos_info.get("name") or "").strip().upper()

            rows.append(
                {
                    "player_name": full_name,
                    "display_name": full_name,
                    "position": position,
                    "team": team["abbr"],
                    "status": _status_from_athlete(athlete),
                    "player_id": player_id,
                    "gsis_id": None,
                    "season": current_season,
                }
            )

    return pd.DataFrame(rows)


def fetch_rosters_for_seasons(seasons: list[int], *, timeout_seconds: int = 10) -> pd.DataFrame:
    base = fetch_current_players(timeout_seconds=timeout_seconds)
    if base.empty:
        return base

    normalized_seasons = [int(s) for s in seasons if isinstance(s, int) or str(s).isdigit()]
    if not normalized_seasons:
        normalized_seasons = [datetime.now(timezone.utc).year]

    frames: list[pd.DataFrame] = []
    for season in normalized_seasons:
        season_df = base.copy()
        season_df["season"] = int(season)
        frames.append(season_df)

    return pd.concat(frames, ignore_index=True)
