from __future__ import annotations

from typing import Any, Dict, List


def _normalize_history_team_key(value: Any) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _owner_label_is_placeholder(owner_label: Any, team_name: Any) -> bool:
    normalized_owner = _normalize_history_team_key(owner_label)
    normalized_team = _normalize_history_team_key(team_name)
    if not normalized_owner or not normalized_team:
        return False
    return normalized_owner == normalized_team


def _safe_record_int(record: Dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = record.get(key)
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _bump_history_gap(
    grouped: Dict[tuple[Any, ...], Dict[str, Any]],
    key: tuple[Any, ...],
    payload: Dict[str, Any],
) -> None:
    if key not in grouped:
        grouped[key] = {**payload, "occurrence_count": 0}
    grouped[key]["occurrence_count"] += 1


def _finalize_history_gap_rows(
    grouped: Dict[tuple[Any, ...], Dict[str, Any]],
    *,
    sort_keys: List[str],
) -> List[Dict[str, Any]]:
    rows = list(grouped.values())
    rows.sort(
        key=lambda row: tuple(
            -int(row.get(key) or 0) if key in {"season", "occurrence_count"} else str(row.get(key) or "")
            for key in sort_keys
        )
    )
    return rows


def build_history_owner_gap_report(
    *,
    league_id: int,
    mapping_rows: List[Any],
    deduped_match_rows: List[Dict[str, Any]],
    deduped_series_rows: List[Dict[str, Any]],
    malformed_match_row_count: int,
    malformed_series_row_count: int,
    detail_limit: int | None = None,
    season_limit: int | None = None,
    logger: Any = None,
) -> Dict[str, Any]:
    placeholder_mappings = [
        {
            "id": row.id,
            "season": int(row.season),
            "team_name": row.team_name,
            "team_name_key": row.team_name_key,
            "owner_name": row.owner_name,
            "owner_id": row.owner_id,
            "notes": row.notes,
        }
        for row in mapping_rows
        if row.owner_name and _owner_label_is_placeholder(row.owner_name, row.team_name)
    ]

    unresolved_match_teams: Dict[tuple[Any, ...], Dict[str, Any]] = {}
    for row in deduped_match_rows:
        season = _safe_record_int(row, "record_year", "season", "year")
        week = _safe_record_int(row, "record_week", "week")
        away_team = str(row.get("away_franchise_raw") or row.get("away_team") or "Unknown").strip()
        home_team = str(row.get("home_franchise_raw") or row.get("home_team") or "Unknown").strip()
        if str(row.get("away_owner_name") or "-") == "-":
            _bump_history_gap(
                unresolved_match_teams,
                (season, _normalize_history_team_key(away_team), "away"),
                {
                    "season": season,
                    "team_name": away_team,
                    "team_name_key": _normalize_history_team_key(away_team),
                    "side": "away",
                    "sample_week": week,
                },
            )
        if str(row.get("home_owner_name") or "-") == "-":
            _bump_history_gap(
                unresolved_match_teams,
                (season, _normalize_history_team_key(home_team), "home"),
                {
                    "season": season,
                    "team_name": home_team,
                    "team_name_key": _normalize_history_team_key(home_team),
                    "side": "home",
                    "sample_week": week,
                },
            )

    unresolved_series_teams: Dict[tuple[Any, ...], Dict[str, Any]] = {}
    unresolved_series_source_tokens: Dict[tuple[Any, ...], Dict[str, Any]] = {}
    for row in deduped_series_rows:
        season = _safe_record_int(row, "series_season", "record_year", "season")
        perspective_team = str(row.get("perspective_team_name") or "").strip()
        opponent_team = str(row.get("opponent_team_name") or row.get("opponent_franchise_raw") or "Unknown").strip()
        source_token = str(row.get("perspective_source_key") or "").strip()
        if str(row.get("perspective_owner_name") or "-") == "-":
            if source_token and source_token != "-":
                _bump_history_gap(
                    unresolved_series_source_tokens,
                    (season, source_token),
                    {
                        "season": season,
                        "source_token": source_token,
                    },
                )
            if perspective_team and perspective_team != "-":
                _bump_history_gap(
                    unresolved_series_teams,
                    (season, _normalize_history_team_key(perspective_team), "perspective"),
                    {
                        "season": season,
                        "team_name": perspective_team,
                        "team_name_key": _normalize_history_team_key(perspective_team),
                        "role": "perspective",
                        "source_token": source_token or None,
                    },
                )
        if str(row.get("opponent_owner_name") or "-") == "-":
            _bump_history_gap(
                unresolved_series_teams,
                (season, _normalize_history_team_key(opponent_team), "opponent"),
                {
                    "season": season,
                    "team_name": opponent_team,
                    "team_name_key": _normalize_history_team_key(opponent_team),
                    "role": "opponent",
                    "source_token": source_token or None,
                },
            )

    unresolved_match_rows = _finalize_history_gap_rows(
        unresolved_match_teams,
        sort_keys=["occurrence_count", "season", "team_name", "side"],
    )
    unresolved_series_team_rows = _finalize_history_gap_rows(
        unresolved_series_teams,
        sort_keys=["occurrence_count", "season", "team_name", "role"],
    )
    unresolved_series_source_token_rows = _finalize_history_gap_rows(
        unresolved_series_source_tokens,
        sort_keys=["occurrence_count", "season", "source_token"],
    )

    season_summary: Dict[int, Dict[str, Any]] = {}

    def bump_season(season: int, key: str, amount: int = 1) -> None:
        if season <= 0:
            return
        row = season_summary.setdefault(
            season,
            {
                "season": season,
                "placeholder_mapping_count": 0,
                "unresolved_match_team_count": 0,
                "unresolved_series_team_count": 0,
                "unresolved_series_source_token_count": 0,
                "occurrence_count": 0,
            },
        )
        row[key] += amount

    for row in placeholder_mappings:
        bump_season(int(row["season"]), "placeholder_mapping_count")
    for row in unresolved_match_rows:
        bump_season(int(row["season"]), "unresolved_match_team_count")
        bump_season(int(row["season"]), "occurrence_count", int(row["occurrence_count"]))
    for row in unresolved_series_team_rows:
        bump_season(int(row["season"]), "unresolved_series_team_count")
        bump_season(int(row["season"]), "occurrence_count", int(row["occurrence_count"]))
    for row in unresolved_series_source_token_rows:
        bump_season(int(row["season"]), "unresolved_series_source_token_count")
        bump_season(int(row["season"]), "occurrence_count", int(row["occurrence_count"]))

    seasons = sorted(season_summary.values(), key=lambda row: (-row["season"], -row["occurrence_count"]))

    full_placeholder_count = len(placeholder_mappings)
    full_unresolved_match_count = len(unresolved_match_rows)
    full_unresolved_series_team_count = len(unresolved_series_team_rows)
    full_unresolved_series_source_count = len(unresolved_series_source_token_rows)
    full_season_count = len(seasons)

    if detail_limit is not None:
        placeholder_mappings = placeholder_mappings[:detail_limit]
        unresolved_match_rows = unresolved_match_rows[:detail_limit]
        unresolved_series_team_rows = unresolved_series_team_rows[:detail_limit]
        unresolved_series_source_token_rows = unresolved_series_source_token_rows[:detail_limit]

    if season_limit is not None:
        seasons = seasons[:season_limit]

    if logger and (malformed_match_row_count or malformed_series_row_count):
        logger.warning(
            "history owner gap report ignored malformed rows",
            extra={
                "league_id": league_id,
                "malformed_match_row_count": malformed_match_row_count,
                "malformed_series_row_count": malformed_series_row_count,
            },
        )

    return {
        "league_id": league_id,
        "summary": {
            "placeholder_mapping_count": full_placeholder_count,
            "unresolved_match_team_count": full_unresolved_match_count,
            "unresolved_series_team_count": full_unresolved_series_team_count,
            "unresolved_series_source_token_count": full_unresolved_series_source_count,
            "season_count": full_season_count,
        },
        "metadata": {
            "response_limits": {
                "detail_limit": detail_limit,
                "season_limit": season_limit,
            },
            "truncated": {
                "placeholder_mappings": detail_limit is not None and full_placeholder_count > len(placeholder_mappings),
                "unresolved_match_teams": detail_limit is not None and full_unresolved_match_count > len(unresolved_match_rows),
                "unresolved_series_teams": detail_limit is not None and full_unresolved_series_team_count > len(unresolved_series_team_rows),
                "unresolved_series_source_tokens": detail_limit is not None and full_unresolved_series_source_count > len(unresolved_series_source_token_rows),
                "seasons": season_limit is not None and full_season_count > len(seasons),
            },
            "ignored_malformed_row_count": {
                "match_records": malformed_match_row_count,
                "series_records": malformed_series_row_count,
            },
        },
        "seasons": seasons,
        "placeholder_mappings": placeholder_mappings,
        "unresolved_match_teams": unresolved_match_rows,
        "unresolved_series_teams": unresolved_series_team_rows,
        "unresolved_series_source_tokens": unresolved_series_source_token_rows,
    }
