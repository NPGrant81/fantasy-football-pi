from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.schemas.live_scoring import (
    ContractInspectionResult,
    NormalizedGame,
    NormalizedLiveScoringPayload,
    NormalizedPlayerStat,
)


REQUIRED_SCOREBOARD_PATHS: tuple[str, ...] = (
    "events",
    "events[].id",
    "events[].season.year",
    "events[].competitions[].date",
    "events[].competitions[].status.type.name",
    "events[].competitions[].competitors[].homeAway",
    "events[].competitions[].competitors[].team.id",
    "events[].competitions[].competitors[].team.abbreviation",
    "events[].competitions[].competitors[].score",
)


def inspect_scoreboard_contract(payload: dict[str, Any]) -> ContractInspectionResult:
    events = payload.get("events")
    required_paths = {
        path: _path_exists(payload, path)
        for path in REQUIRED_SCOREBOARD_PATHS
    }
    missing_paths = [path for path, present in required_paths.items() if not present]
    return ContractInspectionResult(
        required_paths=required_paths,
        missing_paths=missing_paths,
        event_count=len(events) if isinstance(events, list) else 0,
    )


def map_scoreboard_payload(
    payload: dict[str, Any],
    *,
    season_override: int | None = None,
    week_override: int | None = None,
) -> NormalizedLiveScoringPayload:
    games: list[NormalizedGame] = []
    player_stats: list[NormalizedPlayerStat] = []
    events = payload.get("events")
    if not isinstance(events, list):
        return NormalizedLiveScoringPayload(games=[], player_stats=[])

    for event in events:
        game = _map_event_to_game(
            event,
            season_override=season_override,
            week_override=week_override,
        )
        if game is not None:
            games.append(game)
        player_stats.extend(
            _map_event_to_player_stats(
                event,
                season_override=season_override,
                week_override=week_override,
            )
        )

    return NormalizedLiveScoringPayload(games=games, player_stats=_coalesce_player_stats(player_stats))


def to_nfl_game_upsert_rows(normalized: NormalizedLiveScoringPayload) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for game in normalized.games:
        rows.append(
            {
                "event_id": game.event_id,
                "season": game.season,
                "week": game.week,
                "home_team_id": game.home_team_id,
                "away_team_id": game.away_team_id,
                "kickoff": game.kickoff_utc.isoformat() if game.kickoff_utc else None,
                "status": game.status,
                "home_score": game.home_score,
                "away_score": game.away_score,
            }
        )
    return rows


def _map_event_to_game(
    event: dict[str, Any],
    *,
    season_override: int | None,
    week_override: int | None,
) -> NormalizedGame | None:
    event_id = str(event.get("id") or "").strip()
    if not event_id:
        return None

    competitions = event.get("competitions")
    if not isinstance(competitions, list) or not competitions:
        return None

    competition = competitions[0]
    competitors = competition.get("competitors")
    if not isinstance(competitors, list) or len(competitors) < 2:
        return None

    home, away = _resolve_home_away(competitors)
    if home is None or away is None:
        return None

    kickoff_utc = _parse_datetime(competition.get("date") or event.get("date"))

    season, week = _resolve_event_context(
        event,
        competition,
        season_override=season_override,
        week_override=week_override,
    )

    status = str(_read_path(competition, "status.type.name") or "PRE").upper()

    return NormalizedGame(
        event_id=event_id,
        season=season,
        week=week,
        kickoff_utc=kickoff_utc,
        status=status,
        home_team_id=_to_int(_read_path(home, "team.id")),
        away_team_id=_to_int(_read_path(away, "team.id")),
        home_team_abbr=_to_str(_read_path(home, "team.abbreviation")),
        away_team_abbr=_to_str(_read_path(away, "team.abbreviation")),
        home_score=_to_int(_read_path(home, "score"), default=0) or 0,
        away_score=_to_int(_read_path(away, "score"), default=0) or 0,
    )


def _map_event_to_player_stats(
    event: dict[str, Any],
    *,
    season_override: int | None,
    week_override: int | None,
) -> list[NormalizedPlayerStat]:
    event_id = _to_str(event.get("id"))
    if not event_id:
        return []

    competitions = event.get("competitions")
    if not isinstance(competitions, list) or not competitions:
        return []

    competition = competitions[0]
    season, week = _resolve_event_context(
        event,
        competition,
        season_override=season_override,
        week_override=week_override,
    )

    competitors = competition.get("competitors")
    if not isinstance(competitors, list):
        return []

    rows: list[NormalizedPlayerStat] = []
    for competitor in competitors:
        if not isinstance(competitor, dict):
            continue
        team_abbr = _to_str(_read_path(competitor, "team.abbreviation"))
        leaders = competitor.get("leaders")
        if not isinstance(leaders, list):
            continue

        for category in leaders:
            if not isinstance(category, dict):
                continue
            stat_key = _normalize_stat_key(
                category.get("name")
                or category.get("displayName")
                or category.get("shortDisplayName")
            )

            leader_rows = category.get("leaders")
            if not isinstance(leader_rows, list):
                continue

            for leader_entry in leader_rows:
                if not isinstance(leader_entry, dict):
                    continue
                athlete = leader_entry.get("athlete")
                if not isinstance(athlete, dict):
                    continue

                player_espn_id = _to_str(athlete.get("id"))
                player_name = _to_str(athlete.get("displayName") or athlete.get("fullName"))
                if not player_espn_id or not player_name:
                    continue

                value = _to_float(leader_entry.get("value"))
                stats: dict[str, float | int | str] = {}
                if stat_key and value is not None:
                    stats[stat_key] = value

                fantasy_points = value if stat_key and "fantasy" in stat_key and "point" in stat_key else None
                position = _to_str(_read_path(athlete, "position.abbreviation"))

                rows.append(
                    NormalizedPlayerStat(
                        event_id=event_id,
                        season=season,
                        week=week,
                        player_espn_id=player_espn_id,
                        player_name=player_name,
                        team_abbr=team_abbr,
                        position=position,
                        fantasy_points=fantasy_points,
                        stats=stats,
                    )
                )

    return rows


def _coalesce_player_stats(rows: list[NormalizedPlayerStat]) -> list[NormalizedPlayerStat]:
    by_key: dict[tuple[str, str, int | None, int | None], NormalizedPlayerStat] = {}
    for row in rows:
        key = (row.event_id, row.player_espn_id, row.season, row.week)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = row
            continue

        merged_stats = dict(existing.stats or {})
        merged_stats.update(row.stats or {})
        existing.stats = merged_stats

        if existing.fantasy_points is None and row.fantasy_points is not None:
            existing.fantasy_points = row.fantasy_points
        if not existing.position and row.position:
            existing.position = row.position
        if not existing.team_abbr and row.team_abbr:
            existing.team_abbr = row.team_abbr

    return list(by_key.values())


def _resolve_event_context(
    event: dict[str, Any],
    competition: dict[str, Any],
    *,
    season_override: int | None,
    week_override: int | None,
) -> tuple[int | None, int | None]:
    season = season_override
    if season is None:
        season = _to_int(_read_path(event, "season.year"))

    week = week_override
    if week is None:
        week = _to_int(_read_path(competition, "week.number"))

    return season, week


def _resolve_home_away(competitors: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    home = None
    away = None
    for competitor in competitors:
        marker = str(competitor.get("homeAway") or "").lower()
        if marker == "home":
            home = competitor
        elif marker == "away":
            away = competitor
    if home is None and len(competitors) >= 2:
        home = competitors[0]
    if away is None and len(competitors) >= 2:
        away = competitors[1]
    return home, away


def _path_exists(payload: dict[str, Any], path: str) -> bool:
    tokens = path.split(".")
    return _path_exists_from(payload, tokens)


def _path_exists_from(current: Any, tokens: list[str]) -> bool:
    if not tokens:
        return current is not None

    token = tokens[0]
    wants_list = token.endswith("[]")
    key = token[:-2] if wants_list else token

    if not isinstance(current, dict):
        return False

    next_value = current.get(key)
    if next_value is None:
        return False

    if wants_list:
        if not isinstance(next_value, list) or not next_value:
            return False
        remainder = tokens[1:]
        for item in next_value:
            if _path_exists_from(item, remainder):
                return True
        return False

    return _path_exists_from(next_value, tokens[1:])


def _read_path(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for token in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(token)
        if current is None:
            return None
    return current


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    return raw or None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_stat_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().lower().replace(" ", "_")
    return "".join(char for char in normalized if char.isalnum() or char == "_")
