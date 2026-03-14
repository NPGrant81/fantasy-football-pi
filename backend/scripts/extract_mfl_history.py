"""Extract MyFantasyLeague exports into CSV files for migration.

This is the first-pass implementation for issue #257. It focuses on
repeatable extraction with predictable folder output and lightweight
normalization per report type.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


API_BASE = "https://api.myfantasyleague.com"
DEFAULT_REPORT_TYPES = [
    "league",
    "franchises",
    "players",
    "draftResults",
    "rosters",
    "standings",
    "schedule",
    "transactions",
]

# Owner-provided mappings from issue discovery.
KNOWN_LEAGUE_BY_SEASON: dict[int, str] = {
    2002: "51155",
    2003: "52234",
    2004: "46417",
    2005: "20248",
    2006: "22804",
    2007: "14291",
    2008: "48937",
    2009: "24809",
    2010: "10547",
    2011: "15794",
    2012: "33168",
    2013: "16794",
    2014: "23495",
    2015: "43630",
    2016: "38909",
    2017: "38909",
    2018: "38909",
    2019: "38909",
    2020: "38909",
    2021: "38909",
    2022: "38909",
    2023: "11422",
    2024: "11422",
    2025: "11422",
    2026: "11422",
}


@dataclass
class ExtractSummary:
    requested_seasons: list[int]
    extracted_reports: int
    skipped_missing_league_id: int
    failed_reports: int
    output_root: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_seasons": self.requested_seasons,
            "extracted_reports": self.extracted_reports,
            "skipped_missing_league_id": self.skipped_missing_league_id,
            "failed_reports": self.failed_reports,
            "output_root": self.output_root,
        }


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _first_non_empty(row: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["season", "league_id", "source_system", "source_endpoint", "extracted_at_utc"])
        return

    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _meta(season: int, league_id: str, report_type: str, extracted_at: str) -> dict[str, Any]:
    return {
        "season": season,
        "league_id": league_id,
        "source_system": "mfl",
        "source_endpoint": report_type,
        "extracted_at_utc": extracted_at,
    }


def _normalize_league(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    root = payload.get("league") or payload
    row = {
        **_meta(season, league_id, "league", extracted_at),
        "league_name": _first_non_empty(root, ["name", "leagueName"]),
        "franchise_count": len(_as_list(root.get("franchises", {}).get("franchise"))),
        "salary_cap": _first_non_empty(root, ["salaryCapAmount", "salaryCap"]),
        "roster_size": _first_non_empty(root, ["rosterSize", "franchisePlayerLimit"]),
    }
    return [row]


def _normalize_players(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    players = _as_list((payload.get("players") or {}).get("player"))
    for player in players:
        rows.append(
            {
                **_meta(season, league_id, "players", extracted_at),
                "player_mfl_id": _first_non_empty(player, ["id", "player_id"]),
                "player_name": _first_non_empty(player, ["name", "player_name"]),
                "position": _first_non_empty(player, ["position", "pos"]),
                "nfl_team": _first_non_empty(player, ["team", "nfl_team"]),
                "status": _first_non_empty(player, ["status"]),
                "raw_player": json.dumps(player, separators=(",", ":")),
            }
        )
    return rows


def _normalize_franchises(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = payload.get("league") or payload
    franchises = _as_list((root.get("franchises") or {}).get("franchise"))
    for franchise in franchises:
        rows.append(
            {
                **_meta(season, league_id, "franchises", extracted_at),
                "franchise_id": _first_non_empty(franchise, ["id", "franchise_id"]),
                "franchise_name": _first_non_empty(franchise, ["name", "franchise_name"]),
                "owner_name": _first_non_empty(franchise, ["owner_name", "owner", "name"]),
                "owner_email": _first_non_empty(franchise, ["email", "owner_email"]),
                "division": _first_non_empty(franchise, ["division"]),
                "raw_franchise": json.dumps(franchise, separators=(",", ":")),
            }
        )
    return rows


def _normalize_draft_results(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    picks = _as_list((payload.get("draftResults") or {}).get("draftUnit"))
    for pick in picks:
        rows.append(
            {
                **_meta(season, league_id, "draftResults", extracted_at),
                "franchise_id": _first_non_empty(pick, ["franchise", "franchise_id"]),
                "player_mfl_id": _first_non_empty(pick, ["player", "player_id"]),
                "pick_number": _first_non_empty(pick, ["pick", "pickNumber"]),
                "round": _first_non_empty(pick, ["round"]),
                "winning_bid": _first_non_empty(pick, ["cost", "amount", "bid"]),
                "is_keeper_pick": str(_first_non_empty(pick, ["keeper"], "0")).lower() in {"1", "true", "yes"},
                "raw_pick": json.dumps(pick, separators=(",", ":")),
            }
        )
    return rows


def _normalize_rosters(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    franchises = _as_list((payload.get("rosters") or {}).get("franchise"))
    for franchise in franchises:
        franchise_id = _first_non_empty(franchise, ["id", "franchise_id"])
        players = _as_list(franchise.get("player"))
        for player in players:
            if isinstance(player, dict):
                player_id = _first_non_empty(player, ["id", "player_id"])
                roster_status = _first_non_empty(player, ["status", "type"])
            else:
                player_id = player
                roster_status = None

            rows.append(
                {
                    **_meta(season, league_id, "rosters", extracted_at),
                    "franchise_id": franchise_id,
                    "player_mfl_id": player_id,
                    "roster_status": roster_status,
                }
            )
    return rows


def _normalize_standings(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    franchises = _as_list((payload.get("standings") or {}).get("franchise"))
    for franchise in franchises:
        rows.append(
            {
                **_meta(season, league_id, "standings", extracted_at),
                "franchise_id": _first_non_empty(franchise, ["id", "franchise_id"]),
                "wins": _first_non_empty(franchise, ["w", "wins"], 0),
                "losses": _first_non_empty(franchise, ["l", "losses"], 0),
                "ties": _first_non_empty(franchise, ["t", "ties"], 0),
                "points_for": _first_non_empty(franchise, ["pf", "points_for"]),
                "points_against": _first_non_empty(franchise, ["pa", "points_against"]),
                "rank": _first_non_empty(franchise, ["rank"]),
                "raw_standing": json.dumps(franchise, separators=(",", ":")),
            }
        )
    return rows


def _normalize_schedule(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    weeks = _as_list((payload.get("schedule") or {}).get("week"))
    for week_row in weeks:
        week = _first_non_empty(week_row, ["week", "id"])
        matchups = _as_list(week_row.get("matchup"))
        for matchup in matchups:
            rows.append(
                {
                    **_meta(season, league_id, "schedule", extracted_at),
                    "week": week,
                    "home_franchise_id": _first_non_empty(matchup, ["franchise1", "home"]),
                    "away_franchise_id": _first_non_empty(matchup, ["franchise2", "away"]),
                    "home_score": _first_non_empty(matchup, ["score1", "home_score"]),
                    "away_score": _first_non_empty(matchup, ["score2", "away_score"]),
                    "raw_matchup": json.dumps(matchup, separators=(",", ":")),
                }
            )
    return rows


def _normalize_transactions(payload: dict[str, Any], season: int, league_id: str, extracted_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    txs = _as_list((payload.get("transactions") or {}).get("transaction"))
    for tx in txs:
        tx_id = _first_non_empty(tx, ["id", "transaction_id"])
        tx_type = _first_non_empty(tx, ["type", "transaction_type"])
        timestamp = _first_non_empty(tx, ["timestamp", "processed_at"])

        players = _as_list(tx.get("player"))
        if not players:
            rows.append(
                {
                    **_meta(season, league_id, "transactions", extracted_at),
                    "transaction_id": tx_id,
                    "week": _first_non_empty(tx, ["week"]),
                    "franchise_id": _first_non_empty(tx, ["franchise", "franchise_id"]),
                    "transaction_type": tx_type,
                    "player_mfl_id": None,
                    "amount": _first_non_empty(tx, ["amount", "bid"]),
                    "processed_at": timestamp,
                    "raw_transaction": json.dumps(tx, separators=(",", ":")),
                }
            )
            continue

        for player in players:
            if isinstance(player, dict):
                player_id = _first_non_empty(player, ["id", "player_id"])
                franchise_id = _first_non_empty(player, ["franchise", "franchise_id"], _first_non_empty(tx, ["franchise", "franchise_id"]))
            else:
                player_id = player
                franchise_id = _first_non_empty(tx, ["franchise", "franchise_id"])
            rows.append(
                {
                    **_meta(season, league_id, "transactions", extracted_at),
                    "transaction_id": tx_id,
                    "week": _first_non_empty(tx, ["week"]),
                    "franchise_id": franchise_id,
                    "transaction_type": tx_type,
                    "player_mfl_id": player_id,
                    "amount": _first_non_empty(tx, ["amount", "bid"]),
                    "processed_at": timestamp,
                    "raw_transaction": json.dumps(tx, separators=(",", ":")),
                }
            )
    return rows


NORMALIZERS = {
    "league": _normalize_league,
    "franchises": _normalize_franchises,
    "players": _normalize_players,
    "draftResults": _normalize_draft_results,
    "rosters": _normalize_rosters,
    "standings": _normalize_standings,
    "schedule": _normalize_schedule,
    "transactions": _normalize_transactions,
}


def _fetch_json(
    *,
    season: int,
    league_id: str,
    report_type: str,
    timeout_seconds: int,
    session_cookie: str | None,
) -> dict[str, Any]:
    effective_type = "league" if report_type == "franchises" else report_type
    params = {
        "TYPE": effective_type,
        "JSON": 1,
    }
    # players can be global, but passing league id is harmless for consistency.
    params["L"] = league_id

    headers: dict[str, str] = {}
    if session_cookie:
        headers["Cookie"] = session_cookie

    response = requests.get(
        f"{API_BASE}/{season}/export",
        params=params,
        headers=headers,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def run_mfl_history_extract(
    *,
    start_year: int,
    end_year: int,
    report_types: list[str] | None = None,
    output_root: str = "exports/history",
    timeout_seconds: int = 20,
    session_cookie: str | None = None,
) -> dict[str, Any]:
    output_base = Path(output_root)
    report_types = report_types or DEFAULT_REPORT_TYPES
    seasons = list(range(start_year, end_year + 1))

    extracted_reports = 0
    skipped_missing_league_id = 0
    failed_reports = 0

    for season in seasons:
        league_id = KNOWN_LEAGUE_BY_SEASON.get(season)
        if not league_id:
            print(f"[skip] season={season} no known league id mapping")
            skipped_missing_league_id += 1
            continue

        for report_type in report_types:
            extracted_at = datetime.now(timezone.utc).isoformat()
            try:
                payload = _fetch_json(
                    season=season,
                    league_id=league_id,
                    report_type=report_type,
                    timeout_seconds=timeout_seconds,
                    session_cookie=session_cookie,
                )

                raw_path = output_base / "raw" / report_type / f"{season}.json"
                _write_json(raw_path, payload)

                normalizer = NORMALIZERS.get(report_type)
                if normalizer is None:
                    rows = [
                        {
                            **_meta(season, league_id, report_type, extracted_at),
                            "payload_json": json.dumps(payload, separators=(",", ":")),
                        }
                    ]
                else:
                    rows = normalizer(payload, season, league_id, extracted_at)

                csv_path = output_base / report_type / f"{season}.csv"
                _write_csv(csv_path, rows)
                print(f"[ok] season={season} type={report_type} rows={len(rows)}")
                extracted_reports += 1
            except Exception as exc:  # noqa: BLE001 - extraction should continue per report
                failed_reports += 1
                print(f"[error] season={season} type={report_type} {exc}")
                if "football7.myfantasyleague.com" in str(exc):
                    print(
                        "[hint] legacy host football7.myfantasyleague.com did not resolve; "
                        "capture this season via manual export/snapshot and import as CSV"
                    )

    summary = ExtractSummary(
        requested_seasons=seasons,
        extracted_reports=extracted_reports,
        skipped_missing_league_id=skipped_missing_league_id,
        failed_reports=failed_reports,
        output_root=str(output_base),
    )

    summary_path = output_base / "_run_summary.json"
    _write_json(summary_path, summary.to_dict())
    return summary.to_dict()
