"""Extract selected MFL HTML report pages into normalized CSV files.

This is the fallback lane for report pages that are not well-covered by the
structured export API, particularly legacy league history and stats screens.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests

from backend.scripts.extract_mfl_history import API_BASE, KNOWN_LEAGUE_BY_SEASON


KNOWN_REPORT_PAGES: dict[str, dict[str, Any]] = {
    "league_champions": {"option_code": "194", "table_index": 1},
    "league_awards": {"option_code": "202", "table_index": 1},
    "franchise_records": {"option_code": "156", "table_index": 1},
    "player_records": {"option_code": "157", "table_index": 1},
    "matchup_records": {"option_code": "158", "table_index": 1},
    "all_time_series_records": {"option_code": "171", "table_index": 1},
    "season_records": {"option_code": "204", "table_index": 1},
    "career_records": {"option_code": "208", "table_index": 1},
    "record_streaks": {"option_code": "232", "table_index": 1},
    "top_performers_player_stats": {"option_code": "08", "table_index": 1},
    "starter_points_by_position": {"option_code": "23", "table_index": 1},
    "points_allowed_by_position": {"option_code": "81", "table_index": 1},
    "draft_results_detailed": {"option_code": "102", "table_index": 1},
}

DEFAULT_REPORT_PAGES = [
    "league_champions",
    "league_awards",
    "top_performers_player_stats",
    "starter_points_by_position",
    "points_allowed_by_position",
    "draft_results_detailed",
]

KNOWN_HOST_BY_SEASON: dict[int, str] = {
    2002: "https://www47.myfantasyleague.com",
    2003: "https://www44.myfantasyleague.com",
}


@dataclass
class HtmlReportExtractSummary:
    requested_seasons: list[int]
    extracted_reports: int
    skipped_missing_host: int
    skipped_missing_league_id: int
    failed_reports: int
    output_root: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_seasons": self.requested_seasons,
            "extracted_reports": self.extracted_reports,
            "skipped_missing_host": self.skipped_missing_host,
            "skipped_missing_league_id": self.skipped_missing_league_id,
            "failed_reports": self.failed_reports,
            "output_root": self.output_root,
        }


def _slugify_column_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("%", "pct")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "value"


def _flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        flattened: list[str] = []
        for column in frame.columns:
            parts = [str(part).strip() for part in column if str(part).strip() and not str(part).startswith("Unnamed:")]
            flattened.append("_".join(parts) if parts else "value")
        frame.columns = flattened
    else:
        frame.columns = [str(column).strip() for column in frame.columns]

    frame.columns = [_slugify_column_name(column) for column in frame.columns]
    return frame


def _build_report_url(*, host: str, season: int, league_id: str, report_key: str) -> str:
    option_code = KNOWN_REPORT_PAGES[report_key]["option_code"]
    return f"{host}/{season}/options?L={league_id}&O={option_code}"


def _fetch_report_html(*, url: str, timeout_seconds: int, session_cookie: str | None) -> str:
    headers = {
        "User-Agent": "fantasy-football-pi-mfl-html-extractor/0.1",
    }
    if session_cookie:
        headers["Cookie"] = session_cookie
    response = requests.get(url, headers=headers, timeout=timeout_seconds)
    response.raise_for_status()
    return response.text


def _resolve_html_host(*, season: int, league_id: str, timeout_seconds: int) -> str | None:
    known_host = KNOWN_HOST_BY_SEASON.get(season)
    if known_host:
        return known_host

    url = f"{API_BASE}/{season}/export"
    params = {"TYPE": "league", "L": league_id, "JSON": 1}
    try:
        response = requests.get(url, params=params, timeout=timeout_seconds)
        response.raise_for_status()
    except Exception:  # noqa: BLE001
        return None

    parsed = urlparse(response.url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return None


def _name_key(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _parse_detailed_draft_player(value: Any) -> tuple[str | None, str | None, str | None]:
    text = str(value or "").strip()
    if not text:
        return (None, None, None)

    text = re.sub(r"\s+", " ", text)
    parts = text.split(" ")
    if len(parts) < 3:
        return (text, None, None)

    nfl_team = parts[-2].upper()
    position = parts[-1].upper()
    player_name = " ".join(parts[:-2]).strip()
    if not player_name:
        return (None, None, None)
    return (player_name, nfl_team, position)


def _fetch_player_lookup(*, season: int, league_id: str, timeout_seconds: int) -> dict[tuple[str, str, str], str]:
    url = f"{API_BASE}/{season}/export"
    params = {"TYPE": "players", "L": league_id, "JSON": 1}
    response = requests.get(url, params=params, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()

    players = (payload.get("players") or {}).get("player")
    if not isinstance(players, list):
        players = [players] if isinstance(players, dict) else []

    lookup: dict[tuple[str, str, str], str] = {}
    for player in players:
        if not isinstance(player, dict):
            continue
        player_id = str(player.get("id") or "").strip()
        if not player_id:
            continue
        name = _name_key(player.get("name"))
        nfl_team = str(player.get("team") or "").strip().upper()
        position = str(player.get("position") or "").strip().upper()
        if name and nfl_team and position:
            lookup[(name, nfl_team, position)] = player_id
    return lookup


def _extract_draft_results_detailed_table(
    html: str,
    *,
    season: int,
    league_id: str,
    timeout_seconds: int,
) -> pd.DataFrame:
    tables = pd.read_html(StringIO(html))
    table_index = int(KNOWN_REPORT_PAGES["draft_results_detailed"]["table_index"])
    if len(tables) <= table_index:
        raise ValueError(f"expected table index {table_index} for draft_results_detailed, found {len(tables)} tables")

    frame = tables[table_index].copy()
    frame = _flatten_columns(frame)
    frame = frame.dropna(axis=0, how="all").dropna(axis=1, how="all")

    if "player" not in frame.columns:
        raise ValueError("draft_results_detailed table missing expected player column")

    lookup = _fetch_player_lookup(season=season, league_id=league_id, timeout_seconds=timeout_seconds)

    parsed_players = frame["player"].map(_parse_detailed_draft_player)
    frame["player_name"] = parsed_players.map(lambda part: part[0])
    frame["nfl_team"] = parsed_players.map(lambda part: part[1])
    frame["position"] = parsed_players.map(lambda part: part[2])
    frame["player_mfl_id"] = parsed_players.map(
        lambda part: lookup.get((_name_key(part[0]), str(part[1] or "").upper(), str(part[2] or "").upper()))
        if part[0] and part[1] and part[2]
        else None
    )
    return frame


def _extract_report_table(
    html: str,
    *,
    report_key: str,
    season: int,
    league_id: str,
    timeout_seconds: int,
) -> pd.DataFrame:
    if report_key == "draft_results_detailed":
        return _extract_draft_results_detailed_table(
            html,
            season=season,
            league_id=league_id,
            timeout_seconds=timeout_seconds,
        )

    tables = pd.read_html(StringIO(html))
    table_index = int(KNOWN_REPORT_PAGES[report_key]["table_index"])
    if len(tables) <= table_index:
        raise ValueError(f"expected table index {table_index} for {report_key}, found {len(tables)} tables")
    frame = tables[table_index].copy()
    frame = _flatten_columns(frame)
    frame = frame.dropna(axis=0, how="all").dropna(axis=1, how="all")
    return frame


def _write_raw_html(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def _write_dataframe_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _annotate_frame(
    frame: pd.DataFrame,
    *,
    season: int,
    league_id: str,
    report_key: str,
    url: str,
    extracted_at_utc: str,
) -> pd.DataFrame:
    annotated = frame.copy()
    reserved_columns = [
        "season",
        "league_id",
        "source_system",
        "source_endpoint",
        "source_url",
        "extracted_at_utc",
    ]
    rename_map = {
        column: f"report_{column}"
        for column in reserved_columns
        if column in annotated.columns
    }
    if rename_map:
        annotated = annotated.rename(columns=rename_map)

    annotated.insert(0, "extracted_at_utc", extracted_at_utc)
    annotated.insert(0, "source_url", url)
    annotated.insert(0, "source_endpoint", report_key)
    annotated.insert(0, "source_system", "mfl_html")
    annotated.insert(0, "league_id", league_id)
    annotated.insert(0, "season", season)
    return annotated


def run_extract_mfl_html_reports(
    *,
    start_year: int,
    end_year: int,
    report_keys: list[str] | None = None,
    output_root: str = "exports/history_html",
    timeout_seconds: int = 20,
    session_cookie: str | None = None,
) -> dict[str, Any]:
    selected_reports = report_keys or DEFAULT_REPORT_PAGES
    seasons = list(range(start_year, end_year + 1))
    output_base = Path(output_root)

    extracted_reports = 0
    skipped_missing_host = 0
    skipped_missing_league_id = 0
    failed_reports = 0

    host_cache: dict[tuple[int, str], str | None] = {}

    for season in seasons:
        league_id = KNOWN_LEAGUE_BY_SEASON.get(season)
        if not league_id:
            print(f"[skip] season={season} no known league id mapping")
            skipped_missing_league_id += 1
            continue

        host_key = (season, league_id)
        if host_key not in host_cache:
            host_cache[host_key] = _resolve_html_host(
                season=season,
                league_id=league_id,
                timeout_seconds=timeout_seconds,
            )
        host = host_cache[host_key]
        if not host:
            print(f"[skip] season={season} no known HTML host mapping")
            skipped_missing_host += 1
            continue

        for report_key in selected_reports:
            if report_key not in KNOWN_REPORT_PAGES:
                raise ValueError(f"unsupported HTML report key: {report_key}")
            extracted_at_utc = datetime.now(timezone.utc).isoformat()
            try:
                url = _build_report_url(host=host, season=season, league_id=league_id, report_key=report_key)
                html = _fetch_report_html(
                    url=url,
                    timeout_seconds=timeout_seconds,
                    session_cookie=session_cookie,
                )
                frame = _extract_report_table(
                    html,
                    report_key=report_key,
                    season=season,
                    league_id=league_id,
                    timeout_seconds=timeout_seconds,
                )
                annotated = _annotate_frame(
                    frame,
                    season=season,
                    league_id=league_id,
                    report_key=report_key,
                    url=url,
                    extracted_at_utc=extracted_at_utc,
                )

                _write_raw_html(output_base / "raw" / report_key / f"{season}.html", html)
                _write_dataframe_csv(output_base / report_key / f"{season}.csv", annotated)
                print(f"[ok] season={season} report={report_key} rows={len(annotated)}")
                extracted_reports += 1
            except Exception as exc:  # noqa: BLE001
                failed_reports += 1
                print(f"[error] season={season} report={report_key} {exc}")

    summary = HtmlReportExtractSummary(
        requested_seasons=seasons,
        extracted_reports=extracted_reports,
        skipped_missing_host=skipped_missing_host,
        skipped_missing_league_id=skipped_missing_league_id,
        failed_reports=failed_reports,
        output_root=str(output_base),
    )
    _write_json(output_base / "_run_summary.json", summary.to_dict())
    return summary.to_dict()