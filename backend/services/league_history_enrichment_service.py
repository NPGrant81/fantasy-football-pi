from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

from sqlalchemy.orm import Session

from .. import models


def safe_record_int(record: Dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            continue
    return -1


def safe_record_float(record: Dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            continue
    return 0.0


def normalize_history_team_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def owner_label_is_placeholder(owner_label: Any, team_name: Any) -> bool:
    normalized_owner = normalize_history_team_key(owner_label)
    normalized_team = normalize_history_team_key(team_name)
    if not normalized_owner or not normalized_team:
        return False
    return normalized_owner == normalized_team


def resolve_mapped_owner_name(
    *,
    year: int,
    team_name: str,
    map_by_season_key: Dict[tuple[int, str], str],
    map_by_team_key: Dict[str, List[tuple[int, str]]],
    user_owner_by_team_key: Dict[str, str],
) -> str:
    team_key = normalize_history_team_key(team_name)
    if not team_key:
        return "-"
    mapped = map_by_season_key.get((year, team_key))
    if mapped:
        return mapped
    season_candidates = map_by_team_key.get(team_key, [])
    if season_candidates:
        _, nearest_owner = min(
            season_candidates,
            key=lambda item: (abs(item[0] - year), -item[0]),
        )
        if nearest_owner:
            return nearest_owner
    return user_owner_by_team_key.get(team_key, "-")


def build_owner_mapping_indexes(
    db: Session,
    *,
    league_id: int,
) -> tuple[
    Dict[tuple[int, str], str],
    Dict[tuple[int, str], str],
    Dict[str, List[tuple[int, str]]],
    Dict[str, str],
]:
    mapping_rows = (
        db.query(models.LeagueHistoryTeamOwnerMap)
        .filter(models.LeagueHistoryTeamOwnerMap.league_id == league_id)
        .all()
    )
    owner_by_season_key: Dict[tuple[int, str], str] = {}
    team_by_season_key: Dict[tuple[int, str], str] = {}
    owner_by_team_key: Dict[str, List[tuple[int, str]]] = {}
    for mapping in mapping_rows:
        mapping_key = str(mapping.team_name_key or "").strip()
        if not mapping_key:
            continue
        mapping_season = int(mapping.season)
        team_by_season_key[(mapping_season, mapping_key)] = str(mapping.team_name or "").strip() or mapping_key
        linked_owner_label = (
            str(getattr(mapping.owner, "username", "") or "").strip()
            or str(getattr(mapping.owner, "team_name", "") or "").strip()
        )
        mapped_owner_label = str(mapping.owner_name or "").strip()
        owner_label = linked_owner_label or mapped_owner_label
        if mapped_owner_label and owner_label_is_placeholder(mapped_owner_label, mapping.team_name):
            owner_label = linked_owner_label
        if owner_label:
            owner_by_season_key[(mapping_season, mapping_key)] = owner_label
            owner_by_team_key.setdefault(mapping_key, []).append((mapping_season, owner_label))

    for mapping_key, season_rows in owner_by_team_key.items():
        owner_by_team_key[mapping_key] = sorted(season_rows, key=lambda item: item[0])

    user_owner_by_team_key: Dict[str, str] = {}
    users = db.query(models.User).filter(models.User.league_id == league_id).all()
    for user in users:
        owner_label = str(user.username or user.team_name or f"Owner {user.id}").strip()
        for candidate in (user.team_name, user.username):
            key = normalize_history_team_key(candidate)
            if key and key not in user_owner_by_team_key:
                user_owner_by_team_key[key] = owner_label

    return owner_by_season_key, team_by_season_key, owner_by_team_key, user_owner_by_team_key


def extract_mfl_options_token(source_url: Any) -> str:
    raw = str(source_url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        query = parse_qs(parsed.query)
        report_code = str((query.get("O") or query.get("o") or [""])[0]).strip()
        if report_code:
            return normalize_history_team_key(f"mfl_o_{report_code}")
    except Exception:
        return ""
    return ""


def dedupe_and_enrich_all_time_series_records(
    *,
    rows: List[Dict[str, Any]],
    owner_by_season_key: Dict[tuple[int, str], str],
    team_by_season_key: Dict[tuple[int, str], str],
    owner_by_team_key: Dict[str, List[tuple[int, str]]],
    user_owner_by_team_key: Dict[str, str],
    limit: int | None,
) -> List[Dict[str, Any]]:
    deduped: Dict[tuple[Any, ...], Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        season_year = safe_record_int(row, "series_season", "record_year", "season")
        opponent_team = str(row.get("opponent_franchise_raw") or row.get("opponent") or "Unknown").strip()
        perspective_token = extract_mfl_options_token(row.get("source_url") or row.get("source_href"))

        perspective_owner = owner_by_season_key.get((season_year, perspective_token), "-") if perspective_token else "-"
        perspective_team = team_by_season_key.get((season_year, perspective_token), "-") if perspective_token else "-"
        if perspective_owner == "-" and perspective_team != "-":
            perspective_owner = resolve_mapped_owner_name(
                year=season_year,
                team_name=perspective_team,
                map_by_season_key=owner_by_season_key,
                map_by_team_key=owner_by_team_key,
                user_owner_by_team_key=user_owner_by_team_key,
            )

        opponent_owner = resolve_mapped_owner_name(
            year=season_year,
            team_name=opponent_team,
            map_by_season_key=owner_by_season_key,
            map_by_team_key=owner_by_team_key,
            user_owner_by_team_key=user_owner_by_team_key,
        )

        record = dict(row)
        record["perspective_owner_name"] = perspective_owner
        record["perspective_team_name"] = perspective_team
        record["opponent_owner_name"] = opponent_owner
        record["opponent_team_name"] = opponent_team
        record["perspective_source_key"] = perspective_token or "-"

        key = (
            season_year,
            perspective_token or "-",
            normalize_history_team_key(opponent_team),
            str(row.get("season_w_l_t_raw") or "-"),
            str(row.get("total_w_l_t_raw") or "-"),
        )
        if key in deduped:
            continue
        deduped[key] = record

    data = list(deduped.values())
    data.sort(
        key=lambda record: (
            safe_record_float(record, "total_pct"),
            safe_record_int(record, "series_season", "season"),
        ),
        reverse=True,
    )
    if limit is not None:
        return data[:limit]
    return data


def dedupe_and_enrich_match_records(
    *,
    rows: List[Dict[str, Any]],
    map_by_season_key: Dict[tuple[int, str], str],
    map_by_team_key: Dict[str, List[tuple[int, str]]],
    user_owner_by_team_key: Dict[str, str],
    limit: int | None,
) -> List[Dict[str, Any]]:
    deduped: Dict[tuple[Any, ...], Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        year = safe_record_int(row, "record_year", "season", "year")
        week = safe_record_int(row, "record_week", "week")
        away_team = str(row.get("away_franchise_raw") or row.get("away_team") or "Unknown").strip()
        home_team = str(row.get("home_franchise_raw") or row.get("home_team") or "Unknown").strip()
        away_score = safe_record_float(row, "away_points", "away_score")
        home_score = safe_record_float(row, "home_points", "home_score")
        combined = safe_record_float(row, "combined_score", "combined", "total_points")

        key = (
            year,
            week,
            normalize_history_team_key(away_team),
            normalize_history_team_key(home_team),
            round(away_score, 2),
            round(home_score, 2),
            round(combined, 2),
        )
        if key in deduped:
            continue

        record = dict(row)
        if "combined_score" not in record or record.get("combined_score") in (None, ""):
            record["combined_score"] = round(away_score + home_score, 2)

        record["away_owner_name"] = resolve_mapped_owner_name(
            year=year,
            team_name=away_team,
            map_by_season_key=map_by_season_key,
            map_by_team_key=map_by_team_key,
            user_owner_by_team_key=user_owner_by_team_key,
        )
        record["home_owner_name"] = resolve_mapped_owner_name(
            year=year,
            team_name=home_team,
            map_by_season_key=map_by_season_key,
            map_by_team_key=map_by_team_key,
            user_owner_by_team_key=user_owner_by_team_key,
        )
        deduped[key] = record

    data = list(deduped.values())
    data.sort(
        key=lambda record: (
            safe_record_float(record, "combined_score", "combined", "total_points"),
            safe_record_int(record, "record_year", "season", "year"),
            safe_record_int(record, "record_week", "week"),
        ),
        reverse=True,
    )
    if limit is not None:
        return data[:limit]
    return data


def sorted_record_json(
    records: List[Any],
    *,
    sort_keys: List[str] | None = None,
    limit: int | None = None,
) -> List[Dict[str, Any]]:
    data = [r.record_json for r in records if isinstance(r.record_json, dict)]
    if sort_keys:
        data.sort(
            key=lambda row: safe_record_int(row, *sort_keys),
            reverse=True,
        )
    if limit is not None:
        return data[:limit]
    return data
