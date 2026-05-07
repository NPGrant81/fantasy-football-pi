from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.services.live_scoring_contract import (
    inspect_play_by_play_contract,
    inspect_scoreboard_contract,
    inspect_summary_contract,
    map_scoreboard_payload,
    to_nfl_game_upsert_rows,
)
from backend.services.live_scoring_sources import (
    PRIMARY_PLAY_BY_PLAY_SOURCE,
    PRIMARY_SCOREBOARD_SOURCE,
    PRIMARY_SUMMARY_SOURCE,
    build_play_by_play_url,
    build_failover_scoreboard_urls,
    build_primary_scoreboard_url,
    build_summary_url,
    scoreboard_candidate_urls,
)
from backend.services.scoring_service import recalculate_league_week_scores
import models


LOGGER = logging.getLogger(__name__)

RUN_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "ingest_health" / "live_scoring_ingest_runs.jsonl"
RAW_RESPONSE_DIR_PATH = Path(__file__).resolve().parent.parent / "data" / "ingest_raw"

_FETCH_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_FETCH_CACHE_LOCK = threading.Lock()
_REQUEST_LAST_CALL_TS: dict[str, float] = {}
_REQUEST_RATE_LIMIT_LOCK = threading.Lock()


class IngestFetchError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict[str, Any]):
        super().__init__(message)
        self.diagnostics = diagnostics


def _cache_ttl_seconds() -> float:
    return max(0.0, float(os.getenv("LIVE_SCORING_CACHE_TTL_SECONDS", "15")))


def _rate_limit_seconds() -> float:
    return max(0.0, float(os.getenv("LIVE_SCORING_RATE_LIMIT_SECONDS", "0.25")))


def _raw_payload_storage_enabled() -> bool:
    return os.getenv("LIVE_SCORING_STORE_RAW_RESPONSES", "1") == "1"


def _raw_response_max_files() -> int:
    return max(0, int(os.getenv("LIVE_SCORING_RAW_RESPONSE_MAX_FILES", "500")))


def _raw_response_max_age_seconds() -> float:
    return max(0.0, float(os.getenv("LIVE_SCORING_RAW_RESPONSE_MAX_AGE_SECONDS", "604800")))


def _cache_key(source: str, parts: list[str]) -> str:
    base = "|".join([source, *parts])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> dict[str, Any] | None:
    ttl = _cache_ttl_seconds()
    if ttl <= 0:
        return None

    with _FETCH_CACHE_LOCK:
        hit = _FETCH_CACHE.get(key)
        if not hit:
            return None
        ts, payload = hit
        if (time.time() - ts) > ttl:
            _FETCH_CACHE.pop(key, None)
            return None
        return copy.deepcopy(payload)


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    ttl = _cache_ttl_seconds()
    if ttl <= 0:
        return
    with _FETCH_CACHE_LOCK:
        _FETCH_CACHE[key] = (time.time(), copy.deepcopy(payload))


def _respect_rate_limit(source: str) -> None:
    interval = _rate_limit_seconds()
    if interval <= 0:
        return

    sleep_for = 0.0
    now = time.monotonic()
    with _REQUEST_RATE_LIMIT_LOCK:
        last = _REQUEST_LAST_CALL_TS.get(source)
        if last is not None:
            elapsed = now - last
            if elapsed < interval:
                sleep_for = interval - elapsed
        _REQUEST_LAST_CALL_TS[source] = now + sleep_for

    if sleep_for > 0:
        time.sleep(sleep_for)


def _store_raw_payload_snapshot(
    payload: dict[str, Any],
    *,
    source: str,
    suffix: str,
) -> str | None:
    if not _raw_payload_storage_enabled():
        return None

    root = os.getenv("LIVE_SCORING_RAW_RESPONSE_DIR")
    target_root = Path(root) if root else RAW_RESPONSE_DIR_PATH
    target_root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_source = "".join(ch for ch in source if ch.isalnum() or ch in {"_", "-"})
    safe_suffix = "".join(ch for ch in suffix if ch.isalnum() or ch in {"_", "-"})
    path = target_root / f"{ts}_{safe_source}_{safe_suffix}.json"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    try:
        _prune_raw_payload_snapshots(target_root)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("live_scoring.raw_snapshot_prune_failed path=%s error=%s", target_root, exc)
    return str(path)


def _prune_raw_payload_snapshots(target_root: Path) -> dict[str, int]:
    deleted_for_age = 0
    deleted_for_count = 0

    max_age_seconds = _raw_response_max_age_seconds()
    max_files = _raw_response_max_files()
    now = time.time()

    files = [path for path in target_root.glob("*.json") if path.is_file()]
    if max_age_seconds > 0:
        cutoff = now - max_age_seconds
        for path in files:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                deleted_for_age += 1

    files = [path for path in target_root.glob("*.json") if path.is_file()]
    if max_files > 0 and len(files) > max_files:
        files.sort(key=lambda item: item.stat().st_mtime)
        to_delete = files[: len(files) - max_files]
        for path in to_delete:
            path.unlink(missing_ok=True)
            deleted_for_count += 1

    return {
        "deleted_for_age": deleted_for_age,
        "deleted_for_count": deleted_for_count,
    }


def _phase_from_status(status: str | None) -> str:
    value = str(status or "").upper()
    if "HALF" in value:
        return "halftime"
    if "FINAL" in value or value in {"POST", "COMPLETE", "COMPLETED"}:
        return "final"
    if "IN" in value or "PROGRESS" in value or value in {"LIVE", "ACTIVE"}:
        return "live"
    return "pre"


def _build_game_states(normalized_games: list[Any]) -> dict[str, str]:
    states: dict[str, str] = {}
    for game in normalized_games:
        event_id = str(getattr(game, "event_id", "") or "")
        if not event_id:
            continue
        states[event_id] = _phase_from_status(getattr(game, "status", None))
    return states


def _build_scoreboard_fingerprint(normalized: Any) -> str:
    game_rows = []
    for game in normalized.games:
        game_rows.append(
            {
                "event_id": game.event_id,
                "season": game.season,
                "week": game.week,
                "status": game.status,
                "home_team_id": game.home_team_id,
                "away_team_id": game.away_team_id,
                "home_score": game.home_score,
                "away_score": game.away_score,
            }
        )

    stat_rows = []
    for row in normalized.player_stats:
        stat_rows.append(
            {
                "event_id": row.event_id,
                "season": row.season,
                "week": row.week,
                "player_espn_id": row.player_espn_id,
                "fantasy_points": row.fantasy_points,
                "stats": row.stats,
            }
        )

    payload = {
        "games": sorted(game_rows, key=lambda item: str(item["event_id"])),
        "player_stats": sorted(
            stat_rows,
            key=lambda item: (str(item["event_id"]), str(item["player_espn_id"])),
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _find_persisted_ingest_event(
    db: Session,
    *,
    source: str,
    season: int,
    week: int | None,
    scoreboard_fingerprint: str,
) -> models.LiveScoringIngestEvent | None:
    query = db.query(models.LiveScoringIngestEvent).filter(
        models.LiveScoringIngestEvent.source == source,
        models.LiveScoringIngestEvent.season == season,
        models.LiveScoringIngestEvent.scoreboard_fingerprint == scoreboard_fingerprint,
    )
    if week is None:
        query = query.filter(models.LiveScoringIngestEvent.week.is_(None))
    else:
        query = query.filter(models.LiveScoringIngestEvent.week == week)
    return query.one_or_none()


def _persist_ingest_event(
    db: Session,
    *,
    source: str,
    season: int,
    week: int | None,
    scoreboard_fingerprint: str,
    event_count: int,
    game_states: dict[str, str],
    fetch_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    existing = _find_persisted_ingest_event(
        db,
        source=source,
        season=season,
        week=week,
        scoreboard_fingerprint=scoreboard_fingerprint,
    )
    if existing is not None:
        return {
            "persisted": False,
            "event_id": existing.id,
            "created_at": existing.created_at.isoformat() if existing.created_at else None,
            "reason": "already_exists",
        }

    record = models.LiveScoringIngestEvent(
        source=source,
        season=season,
        week=week,
        scoreboard_fingerprint=scoreboard_fingerprint,
        event_count=event_count,
        game_states=game_states,
        fetch_diagnostics=fetch_diagnostics,
        raw_response_path=fetch_diagnostics.get("raw_response_path"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "persisted": True,
        "event_id": record.id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def build_scoreboard_url(year: int, week: int | None = None) -> str:
    return build_primary_scoreboard_url(year, week)


def _backup_scoreboard_url(year: int, week: int | None = None) -> str:
    return build_failover_scoreboard_urls(year, week)[0]


def _candidate_urls(
    year: int,
    week: int | None,
    *,
    override_url: str | None,
    enable_failover: bool,
) -> list[str]:
    return scoreboard_candidate_urls(
        year,
        week,
        override_url=override_url,
        enable_failover=enable_failover,
    )


def fetch_scoreboard_payload_with_diagnostics(
    year: int,
    week: int | None = None,
    *,
    timeout_seconds: int = 30,
    override_url: str | None = None,
    enable_failover: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cache_key = _cache_key(
        PRIMARY_SCOREBOARD_SOURCE,
        [str(year), str(week) if week is not None else "all"],
    )
    cache_hit = _cache_get(cache_key)
    if cache_hit is not None:
        diagnostics = {
            "mode": "cache",
            "source": PRIMARY_SCOREBOARD_SOURCE,
            "year": year,
            "week": week,
            "cache_hit": True,
            "degraded": False,
        }
        return cache_hit, diagnostics

    attempts: list[dict[str, Any]] = []
    urls = _candidate_urls(
        year,
        week,
        override_url=override_url,
        enable_failover=enable_failover,
    )

    for index, url in enumerate(urls, start=1):
        start = time.perf_counter()
        attempt: dict[str, Any] = {
            "attempt": index,
            "url": url,
            "status": "unknown",
            "status_code": None,
            "latency_ms": None,
            "error": None,
        }
        try:
            LOGGER.info("live_scoring.fetch_scoreboard year=%s week=%s url=%s attempt=%s", year, week, url, index)
            _respect_rate_limit(PRIMARY_SCOREBOARD_SOURCE)
            response = requests.get(url, timeout=timeout_seconds)
            attempt["status_code"] = response.status_code
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("ESPN scoreboard payload must be a JSON object")
            _cache_set(cache_key, payload)
            raw_path = _store_raw_payload_snapshot(
                payload,
                source=PRIMARY_SCOREBOARD_SOURCE,
                suffix=f"{year}_{week if week is not None else 'all'}",
            )

            attempt["status"] = "success"
            attempt["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
            attempts.append(attempt)

            diagnostics = {
                "mode": "live_fetch",
                "source": PRIMARY_SCOREBOARD_SOURCE,
                "year": year,
                "week": week,
                "timeout_seconds": timeout_seconds,
                "urls_considered": urls,
                "attempts": attempts,
                "used_url": url,
                "failover_used": index > 1,
                "degraded": index > 1,
                "cache_hit": False,
                "raw_response_path": raw_path,
            }
            return payload, diagnostics
        except Exception as exc:  # noqa: BLE001 - intentionally surfaced in diagnostics
            attempt["status"] = "failed"
            attempt["error"] = f"{type(exc).__name__}: {exc}"
            attempt["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
            attempts.append(attempt)
            LOGGER.warning("live_scoring.fetch_attempt_failed url=%s attempt=%s error=%s", url, index, attempt["error"])

    diagnostics = {
        "mode": "live_fetch",
        "source": PRIMARY_SCOREBOARD_SOURCE,
        "year": year,
        "week": week,
        "timeout_seconds": timeout_seconds,
        "urls_considered": urls,
        "attempts": attempts,
        "used_url": None,
        "failover_used": len(attempts) > 1,
        "degraded": True,
    }
    raise IngestFetchError("Unable to fetch ESPN scoreboard payload from all candidates", diagnostics)


def fetch_scoreboard_payload(
    year: int,
    week: int | None = None,
    timeout_seconds: int = 30,
    override_url: str | None = None,
    enable_failover: bool = True,
) -> dict[str, Any]:
    payload, _ = fetch_scoreboard_payload_with_diagnostics(
        year=year,
        week=week,
        timeout_seconds=timeout_seconds,
        override_url=override_url,
        enable_failover=enable_failover,
    )
    return payload


def fetch_summary_payload_with_diagnostics(
    event_id: str,
    *,
    timeout_seconds: int = 30,
    override_url: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cache_key = _cache_key(PRIMARY_SUMMARY_SOURCE, [str(event_id)])
    cache_hit = _cache_get(cache_key)
    if cache_hit is not None:
        return cache_hit, {
            "mode": "cache",
            "source": PRIMARY_SUMMARY_SOURCE,
            "event_id": event_id,
            "cache_hit": True,
            "status": "success",
        }

    url = override_url or build_summary_url(event_id)
    start = time.perf_counter()
    try:
        _respect_rate_limit(PRIMARY_SUMMARY_SOURCE)
        response = requests.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("ESPN summary payload must be a JSON object")
        _cache_set(cache_key, payload)
        raw_path = _store_raw_payload_snapshot(
            payload,
            source=PRIMARY_SUMMARY_SOURCE,
            suffix=event_id,
        )
        diagnostics = {
            "mode": "live_fetch",
            "source": PRIMARY_SUMMARY_SOURCE,
            "event_id": event_id,
            "url": url,
            "status": "success",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "cache_hit": False,
            "raw_response_path": raw_path,
        }
        return payload, diagnostics
    except Exception as exc:  # noqa: BLE001
        diagnostics = {
            "mode": "live_fetch",
            "source": PRIMARY_SUMMARY_SOURCE,
            "event_id": event_id,
            "url": url,
            "status": "failed",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "error": f"{type(exc).__name__}: {exc}",
        }
        raise IngestFetchError("Unable to fetch ESPN summary payload", diagnostics) from exc


def fetch_play_by_play_payload_with_diagnostics(
    event_id: str,
    *,
    timeout_seconds: int = 30,
    override_url: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cache_key = _cache_key(PRIMARY_PLAY_BY_PLAY_SOURCE, [str(event_id)])
    cache_hit = _cache_get(cache_key)
    if cache_hit is not None:
        return cache_hit, {
            "mode": "cache",
            "source": PRIMARY_PLAY_BY_PLAY_SOURCE,
            "event_id": event_id,
            "cache_hit": True,
            "status": "success",
        }

    url = override_url or build_play_by_play_url(event_id)
    start = time.perf_counter()
    try:
        _respect_rate_limit(PRIMARY_PLAY_BY_PLAY_SOURCE)
        response = requests.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("ESPN play-by-play payload must be a JSON object")
        _cache_set(cache_key, payload)
        raw_path = _store_raw_payload_snapshot(
            payload,
            source=PRIMARY_PLAY_BY_PLAY_SOURCE,
            suffix=event_id,
        )
        diagnostics = {
            "mode": "live_fetch",
            "source": PRIMARY_PLAY_BY_PLAY_SOURCE,
            "event_id": event_id,
            "url": url,
            "status": "success",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "cache_hit": False,
            "raw_response_path": raw_path,
        }
        return payload, diagnostics
    except Exception as exc:  # noqa: BLE001
        diagnostics = {
            "mode": "live_fetch",
            "source": PRIMARY_PLAY_BY_PLAY_SOURCE,
            "event_id": event_id,
            "url": url,
            "status": "failed",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "error": f"{type(exc).__name__}: {exc}",
        }
        raise IngestFetchError("Unable to fetch ESPN play-by-play payload", diagnostics) from exc


def inspect_event_contracts(
    event_id: str,
    *,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    summary_result: dict[str, Any]
    pbp_result: dict[str, Any]

    try:
        summary_payload, summary_diag = fetch_summary_payload_with_diagnostics(
            event_id,
            timeout_seconds=timeout_seconds,
        )
        summary_report = inspect_summary_contract(summary_payload)
        summary_result = {
            "status": "success",
            "diagnostics": summary_diag,
            "missing_required_paths_count": len(summary_report.missing_paths),
            "missing_required_paths": summary_report.missing_paths,
            "event_count": summary_report.event_count,
        }
    except IngestFetchError as exc:
        summary_result = {
            "status": "failed",
            "diagnostics": exc.diagnostics,
            "missing_required_paths_count": None,
            "missing_required_paths": [],
            "event_count": 0,
            "error_signature": type(exc).__name__,
        }

    try:
        pbp_payload, pbp_diag = fetch_play_by_play_payload_with_diagnostics(
            event_id,
            timeout_seconds=timeout_seconds,
        )
        pbp_report = inspect_play_by_play_contract(pbp_payload)
        pbp_result = {
            "status": "success",
            "diagnostics": pbp_diag,
            "missing_required_paths_count": len(pbp_report.missing_paths),
            "missing_required_paths": pbp_report.missing_paths,
            "event_count": pbp_report.event_count,
        }
    except IngestFetchError as exc:
        pbp_result = {
            "status": "failed",
            "diagnostics": exc.diagnostics,
            "missing_required_paths_count": None,
            "missing_required_paths": [],
            "event_count": 0,
            "error_signature": type(exc).__name__,
        }

    degraded = (
        summary_result["status"] != "success"
        or pbp_result["status"] != "success"
        or (summary_result.get("missing_required_paths_count") or 0) > 0
        or (pbp_result.get("missing_required_paths_count") or 0) > 0
    )

    return {
        "event_id": event_id,
        "summary": summary_result,
        "play_by_play": pbp_result,
        "degraded": degraded,
    }


def _append_ingest_run_log(entry: dict[str, Any]) -> None:
    RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, default=str) + "\n")


def load_recent_ingest_runs(limit: int = 100) -> list[dict[str, Any]]:
    if limit <= 0 or not RUN_LOG_PATH.exists():
        return []
    with RUN_LOG_PATH.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
    selected = lines[-limit:]
    rows: list[dict[str, Any]] = []
    for line in selected:
        raw = line.strip()
        if not raw:
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return rows


def summarize_ingest_health(limit: int = 100) -> dict[str, Any]:
    runs = load_recent_ingest_runs(limit=limit)
    if not runs:
        return {
            "runs_considered": 0,
            "success_runs": 0,
            "failed_runs": 0,
            "degraded_runs": 0,
            "failure_rate": 0.0,
            "last_run": None,
            "top_error_signatures": [],
            "runs": [],
        }

    success_runs = [run for run in runs if run.get("status") == "success"]
    failed_runs = [run for run in runs if run.get("status") == "failed"]
    degraded_runs = [run for run in runs if run.get("degraded") is True]

    error_counts: dict[str, int] = {}
    for run in failed_runs:
        signature = str(run.get("error_signature") or "unknown")
        error_counts[signature] = error_counts.get(signature, 0) + 1

    top_error_signatures = [
        {"error_signature": signature, "count": count}
        for signature, count in sorted(error_counts.items(), key=lambda item: item[1], reverse=True)
    ]

    return {
        "runs_considered": len(runs),
        "success_runs": len(success_runs),
        "failed_runs": len(failed_runs),
        "degraded_runs": len(degraded_runs),
        "failure_rate": round(len(failed_runs) / len(runs), 4),
        "last_run": runs[-1],
        "top_error_signatures": top_error_signatures,
        "runs": runs,
    }


def upsert_nfl_games_from_payload(
    db: Session,
    payload: dict[str, Any],
    *,
    season_override: int | None = None,
    week_override: int | None = None,
) -> dict[str, Any]:
    inspection = inspect_scoreboard_contract(payload)
    normalized = map_scoreboard_payload(
        payload,
        season_override=season_override,
        week_override=week_override,
    )
    rows = to_nfl_game_upsert_rows(normalized)

    inserted = 0
    updated = 0

    try:
        for row in rows:
            event_id = row.get("event_id")
            if not event_id:
                continue

            existing = (
                db.query(models.NFLGame)
                .filter(models.NFLGame.event_id == event_id)
                .one_or_none()
            )
            if existing is None:
                db.add(models.NFLGame(**row))
                inserted += 1
                continue

            for key, value in row.items():
                setattr(existing, key, value)
            updated += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    result = {
        "source": PRIMARY_SCOREBOARD_SOURCE,
        "fetched_events": inspection.event_count,
        "normalized_games": len(rows),
        "inserted": inserted,
        "updated": updated,
        "missing_required_paths_count": len(inspection.missing_paths),
        "missing_required_paths": inspection.missing_paths,
    }
    LOGGER.info(
        "live_scoring.ingest_result fetched=%s normalized=%s inserted=%s updated=%s missing_paths=%s",
        result["fetched_events"],
        result["normalized_games"],
        result["inserted"],
        result["updated"],
        result["missing_required_paths_count"],
    )
    return result


def upsert_player_weekly_stats_from_payload(
    db: Session,
    payload: dict[str, Any],
    *,
    season_override: int | None = None,
    week_override: int | None = None,
    source: str = "espn_live_ingest",
) -> dict[str, Any]:
    normalized = map_scoreboard_payload(
        payload,
        season_override=season_override,
        week_override=week_override,
    )

    espn_ids = sorted({row.player_espn_id for row in normalized.player_stats if row.player_espn_id})
    if not espn_ids:
        return {
            "normalized_player_rows": 0,
            "inserted": 0,
            "updated": 0,
            "unmatched_players": 0,
            "skipped_without_context": 0,
            "affected_player_ids": [],
            "affected_weeks": [],
        }

    players = db.query(models.Player).filter(models.Player.espn_id.in_(espn_ids)).all()
    player_by_espn = {str(player.espn_id): player for player in players if player.espn_id}

    inserted = 0
    updated = 0
    unmatched_players = 0
    skipped_without_context = 0
    affected_player_ids: set[int] = set()
    affected_weeks: set[int] = set()

    for row in normalized.player_stats:
        player = player_by_espn.get(row.player_espn_id)
        if player is None:
            unmatched_players += 1
            continue

        season = row.season if row.season is not None else season_override
        week = row.week if row.week is not None else week_override
        if season is None or week is None:
            skipped_without_context += 1
            continue

        existing = (
            db.query(models.PlayerWeeklyStat)
            .filter(
                models.PlayerWeeklyStat.player_id == player.id,
                models.PlayerWeeklyStat.season == season,
                models.PlayerWeeklyStat.week == week,
                models.PlayerWeeklyStat.source == source,
            )
            .one_or_none()
        )

        merged_stats = dict(row.stats or {})
        if existing is None:
            db.add(
                models.PlayerWeeklyStat(
                    player_id=player.id,
                    season=season,
                    week=week,
                    fantasy_points=row.fantasy_points,
                    stats=merged_stats,
                    source=source,
                )
            )
            inserted += 1
        else:
            payload_stats = dict(existing.stats or {})
            payload_stats.update(merged_stats)
            existing.stats = payload_stats
            if row.fantasy_points is not None:
                existing.fantasy_points = row.fantasy_points
            updated += 1

        affected_player_ids.add(int(player.id))
        affected_weeks.add(int(week))

    db.commit()

    return {
        "normalized_player_rows": len(normalized.player_stats),
        "inserted": inserted,
        "updated": updated,
        "unmatched_players": unmatched_players,
        "skipped_without_context": skipped_without_context,
        "affected_player_ids": sorted(affected_player_ids),
        "affected_weeks": sorted(affected_weeks),
    }


def _starter_projected_points(
    db: Session,
    *,
    owner_id: int | None,
    league_id: int,
) -> float:
    if owner_id is None:
        return 0.0

    picks = (
        db.query(models.DraftPick)
        .filter(
            models.DraftPick.owner_id == owner_id,
            models.DraftPick.current_status == "STARTER",
            models.DraftPick.is_taxi.is_(False),
            models.DraftPick.league_id == league_id,
            models.DraftPick.player_id.is_not(None),
        )
        .all()
    )
    if not picks:
        return 0.0

    player_ids = [int(pick.player_id) for pick in picks if pick.player_id is not None]
    players = db.query(models.Player).filter(models.Player.id.in_(player_ids)).all()
    projected_by_player_id = {int(player.id): float(player.projected_points or 0.0) for player in players}

    return round(sum(projected_by_player_id.get(player_id, 0.0) for player_id in player_ids), 4)


def _win_probabilities(home_projected: float, away_projected: float) -> tuple[float, float]:
    home_value = max(float(home_projected or 0.0), 0.0)
    away_value = max(float(away_projected or 0.0), 0.0)
    total = home_value + away_value
    if total <= 0:
        return 50.0, 50.0
    home_probability = round((home_value / total) * 100, 1)
    away_probability = round(100.0 - home_probability, 1)
    return home_probability, away_probability


def reconcile_ingested_stats_and_matchups(
    db: Session,
    *,
    affected_player_ids: set[int],
    season: int,
    week: int | None = None,
    season_year: int | None = None,
    affected_weeks: set[int] | None = None,
) -> dict[str, Any]:
    if not affected_player_ids:
        return {
            "leagues_touched": 0,
            "weeks_touched": 0,
            "matchups_recalculated": 0,
            "league_week_pairs": [],
        }

    starter_picks = (
        db.query(models.DraftPick)
        .filter(
            models.DraftPick.player_id.in_(sorted(affected_player_ids)),
            models.DraftPick.current_status == "STARTER",
            models.DraftPick.is_taxi.is_(False),
            models.DraftPick.league_id.is_not(None),
        )
        .all()
    )
    league_ids = sorted({int(pick.league_id) for pick in starter_picks if pick.league_id is not None})
    if not league_ids:
        return {
            "leagues_touched": 0,
            "weeks_touched": 0,
            "matchups_recalculated": 0,
            "league_week_pairs": [],
        }

    if week is not None:
        weeks = {int(week)}
    elif affected_weeks:
        weeks = {int(item) for item in affected_weeks}
    else:
        week_rows = (
            db.query(models.PlayerWeeklyStat.week)
            .filter(
                models.PlayerWeeklyStat.season == season,
                models.PlayerWeeklyStat.player_id.in_(sorted(affected_player_ids)),
            )
            .distinct()
            .all()
        )
        weeks = {int(item[0]) for item in week_rows if item and item[0] is not None}

    if not weeks:
        return {
            "leagues_touched": len(league_ids),
            "weeks_touched": 0,
            "matchups_recalculated": 0,
            "league_week_pairs": [],
        }

    league_week_pairs: list[dict[str, int]] = []
    matchup_projection_snapshots: list[dict[str, Any]] = []
    total_recalculated = 0
    for league_id in league_ids:
        for target_week in sorted(weeks):
            matchups = (
                db.query(models.Matchup)
                .filter(
                    models.Matchup.league_id == league_id,
                    models.Matchup.week == target_week,
                )
                .all()
            )
            if not matchups:
                continue

            recalculated = recalculate_league_week_scores(
                db,
                league_id=league_id,
                week=target_week,
                season=season,
                season_year=season_year,
            )
            total_recalculated += len(recalculated)
            league_week_pairs.append({"league_id": league_id, "week": target_week})

            for matchup in matchups:
                home_projected = _starter_projected_points(
                    db,
                    owner_id=matchup.home_team_id,
                    league_id=league_id,
                )
                away_projected = _starter_projected_points(
                    db,
                    owner_id=matchup.away_team_id,
                    league_id=league_id,
                )
                home_win_probability, away_win_probability = _win_probabilities(home_projected, away_projected)
                matchup_projection_snapshots.append(
                    {
                        "matchup_id": matchup.id,
                        "league_id": league_id,
                        "week": target_week,
                        "home_projected": home_projected,
                        "away_projected": away_projected,
                        "home_win_probability": home_win_probability,
                        "away_win_probability": away_win_probability,
                    }
                )

    db.commit()

    return {
        "leagues_touched": len({item["league_id"] for item in league_week_pairs}),
        "weeks_touched": len({item["week"] for item in league_week_pairs}),
        "matchups_recalculated": total_recalculated,
        "league_week_pairs": league_week_pairs,
        "matchup_projection_snapshots": matchup_projection_snapshots,
    }


def ingest_scoreboard_into_db(db: Session, year: int, week: int | None = None) -> dict[str, Any]:
    payload, fetch_diagnostics = fetch_scoreboard_payload_with_diagnostics(year=year, week=week)

    game_result = upsert_nfl_games_from_payload(
        db,
        payload,
        season_override=year,
        week_override=week,
    )

    player_result = upsert_player_weekly_stats_from_payload(
        db,
        payload,
        season_override=year,
        week_override=week,
    )

    reconcile_result = reconcile_ingested_stats_and_matchups(
        db,
        affected_player_ids=set(player_result["affected_player_ids"]),
        season=year,
        week=week,
        season_year=year,
        affected_weeks=set(player_result["affected_weeks"]),
    )

    return {
        **game_result,
        "player_stats": player_result,
        "reconciliation": reconcile_result,
        "fetch_diagnostics": fetch_diagnostics,
        "degraded": bool(fetch_diagnostics.get("degraded")) or game_result.get("missing_required_paths_count", 0) > 0,
    }


def run_live_scoreboard_ingest_with_controls(
    *,
    year: int,
    week: int | None = None,
    dry_run: bool = False,
    timeout_seconds: int = 30,
    override_url: str | None = None,
    enable_failover: bool = True,
    inspect_event_contracts_enabled: bool = True,
    event_contracts_limit: int = 3,
    change_guard_fingerprint: str | None = None,
) -> dict[str, Any]:
    run_started_at = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        payload, fetch_diagnostics = fetch_scoreboard_payload_with_diagnostics(
            year=year,
            week=week,
            timeout_seconds=timeout_seconds,
            override_url=override_url,
            enable_failover=enable_failover,
        )

        inspection = inspect_scoreboard_contract(payload)
        normalized = map_scoreboard_payload(payload, season_override=year, week_override=week)
        scoreboard_fingerprint = _build_scoreboard_fingerprint(normalized)
        game_states = _build_game_states(normalized.games)
        change_detected = (
            change_guard_fingerprint is None
            or scoreboard_fingerprint != change_guard_fingerprint
        )
        degraded = bool(fetch_diagnostics.get("degraded")) or len(inspection.missing_paths) > 0

        event_contracts: list[dict[str, Any]] = []
        if inspect_event_contracts_enabled:
            candidate_event_ids: list[str] = []
            for item in normalized.games:
                if item.event_id and item.event_id not in candidate_event_ids:
                    candidate_event_ids.append(item.event_id)
            for event_id in candidate_event_ids[: max(0, event_contracts_limit)]:
                event_contracts.append(
                    inspect_event_contracts(event_id, timeout_seconds=timeout_seconds)
                )
            if any(result.get("degraded") for result in event_contracts):
                degraded = True

        duplicate_ingest_event = None
        if not dry_run and change_detected:
            duplicate_ingest_event = _find_persisted_ingest_event(
                db,
                source=PRIMARY_SCOREBOARD_SOURCE,
                season=year,
                week=week,
                scoreboard_fingerprint=scoreboard_fingerprint,
            )

        if dry_run:
            result = {
                "status": "success",
                "mode": "dry_run",
                "source": PRIMARY_SCOREBOARD_SOURCE,
                "year": year,
                "week": week,
                "fetched_events": inspection.event_count,
                "normalized_games": len(normalized.games),
                "normalized_player_rows": len(normalized.player_stats),
                "missing_required_paths_count": len(inspection.missing_paths),
                "missing_required_paths": inspection.missing_paths,
                "fetch_diagnostics": fetch_diagnostics,
                "event_contracts": event_contracts,
                "degraded": degraded,
                "scoreboard_fingerprint": scoreboard_fingerprint,
                "game_states": game_states,
                "change_detected": change_detected,
                "downstream_updates_triggered": False,
            }
        elif not change_detected:
            result = {
                "status": "success",
                "mode": "apply_skipped",
                "source": PRIMARY_SCOREBOARD_SOURCE,
                "year": year,
                "week": week,
                "fetched_events": inspection.event_count,
                "normalized_games": len(normalized.games),
                "normalized_player_rows": len(normalized.player_stats),
                "missing_required_paths_count": len(inspection.missing_paths),
                "missing_required_paths": inspection.missing_paths,
                "fetch_diagnostics": fetch_diagnostics,
                "event_contracts": event_contracts,
                "degraded": degraded,
                "scoreboard_fingerprint": scoreboard_fingerprint,
                "game_states": game_states,
                "change_detected": False,
                "downstream_updates_triggered": False,
            }
        elif duplicate_ingest_event is not None:
            result = {
                "status": "success",
                "mode": "apply_skipped",
                "source": PRIMARY_SCOREBOARD_SOURCE,
                "year": year,
                "week": week,
                "fetched_events": inspection.event_count,
                "normalized_games": len(normalized.games),
                "normalized_player_rows": len(normalized.player_stats),
                "missing_required_paths_count": len(inspection.missing_paths),
                "missing_required_paths": inspection.missing_paths,
                "fetch_diagnostics": fetch_diagnostics,
                "event_contracts": event_contracts,
                "degraded": degraded,
                "scoreboard_fingerprint": scoreboard_fingerprint,
                "game_states": game_states,
                "change_detected": False,
                "skip_reason": "persisted_idempotency_guard",
                "downstream_updates_triggered": False,
                "ingest_event": {
                    "persisted": False,
                    "event_id": duplicate_ingest_event.id,
                    "created_at": duplicate_ingest_event.created_at.isoformat() if duplicate_ingest_event.created_at else None,
                    "reason": "already_exists",
                },
            }
        else:
            game_result = upsert_nfl_games_from_payload(
                db,
                payload,
                season_override=year,
                week_override=week,
            )
            player_result = upsert_player_weekly_stats_from_payload(
                db,
                payload,
                season_override=year,
                week_override=week,
            )
            reconcile_result = reconcile_ingested_stats_and_matchups(
                db,
                affected_player_ids=set(player_result["affected_player_ids"]),
                season=year,
                week=week,
                season_year=year,
                affected_weeks=set(player_result["affected_weeks"]),
            )
            ingest_event = _persist_ingest_event(
                db,
                source=PRIMARY_SCOREBOARD_SOURCE,
                season=year,
                week=week,
                scoreboard_fingerprint=scoreboard_fingerprint,
                event_count=inspection.event_count,
                game_states=game_states,
                fetch_diagnostics=fetch_diagnostics,
            )
            result = {
                "status": "success",
                "mode": "apply",
                "source": PRIMARY_SCOREBOARD_SOURCE,
                "year": year,
                "week": week,
                **game_result,
                "player_stats": player_result,
                "reconciliation": reconcile_result,
                "fetch_diagnostics": fetch_diagnostics,
                "event_contracts": event_contracts,
                "degraded": degraded,
                "scoreboard_fingerprint": scoreboard_fingerprint,
                "game_states": game_states,
                "change_detected": True,
                "downstream_updates_triggered": True,
                "ingest_event": ingest_event,
            }

        _append_ingest_run_log(
            {
                "timestamp": run_started_at.isoformat(),
                "status": result["status"],
                "mode": result["mode"],
                "year": year,
                "week": week,
                "degraded": result.get("degraded", False),
                "missing_required_paths_count": result.get("missing_required_paths_count", 0),
                "fetched_events": result.get("fetched_events", 0),
                "normalized_games": result.get("normalized_games", 0),
                "normalized_player_rows": result.get("normalized_player_rows", 0)
                if result.get("mode") == "dry_run"
                else result.get("player_stats", {}).get("normalized_player_rows", 0),
                "fetch_attempts": result.get("fetch_diagnostics", {}).get("attempts", []),
                "used_url": result.get("fetch_diagnostics", {}).get("used_url"),
                "failover_used": result.get("fetch_diagnostics", {}).get("failover_used", False),
            }
        )

        return result
    except IngestFetchError as exc:
        failure = {
            "status": "failed",
            "mode": "dry_run" if dry_run else "apply",
            "source": PRIMARY_SCOREBOARD_SOURCE,
            "year": year,
            "week": week,
            "degraded": True,
            "error": str(exc),
            "error_signature": type(exc).__name__,
            "fetch_diagnostics": exc.diagnostics,
        }
        _append_ingest_run_log(
            {
                "timestamp": run_started_at.isoformat(),
                **failure,
            }
        )
        raise
    except Exception as exc:  # noqa: BLE001
        failure = {
            "status": "failed",
            "mode": "dry_run" if dry_run else "apply",
            "source": PRIMARY_SCOREBOARD_SOURCE,
            "year": year,
            "week": week,
            "degraded": True,
            "error": str(exc),
            "error_signature": type(exc).__name__,
        }
        _append_ingest_run_log(
            {
                "timestamp": run_started_at.isoformat(),
                **failure,
            }
        )
        raise
    finally:
        db.close()


def run_live_scoreboard_ingest(year: int, week: int | None = None) -> dict[str, Any]:
    return run_live_scoreboard_ingest_with_controls(year=year, week=week)
