from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.services.live_scoring_contract import (
    inspect_scoreboard_contract,
    map_scoreboard_payload,
    to_nfl_game_upsert_rows,
)
from backend.services.scoring_service import recalculate_league_week_scores
import models


LOGGER = logging.getLogger(__name__)

RUN_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "ingest_health" / "live_scoring_ingest_runs.jsonl"


class IngestFetchError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict[str, Any]):
        super().__init__(message)
        self.diagnostics = diagnostics


def build_scoreboard_url(year: int, week: int | None = None) -> str:
    if week is None:
        return f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?limit=1000&dates={year}"
    return f"https://cdn.espn.com/core/nfl/schedule?xhr=1&year={year}&week={week}"


def _backup_scoreboard_url(year: int, week: int | None = None) -> str:
    if week is None:
        return f"https://cdn.espn.com/core/nfl/scoreboard?xhr=1&year={year}"
    return f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?limit=1000&dates={year}&seasontype=2&week={week}"


def _candidate_urls(
    year: int,
    week: int | None,
    *,
    override_url: str | None,
    enable_failover: bool,
) -> list[str]:
    urls: list[str] = []
    if override_url:
        urls.append(override_url)
    urls.append(build_scoreboard_url(year, week))
    if enable_failover:
        backup = _backup_scoreboard_url(year, week)
        if backup not in urls:
            urls.append(backup)
    return urls


def fetch_scoreboard_payload_with_diagnostics(
    year: int,
    week: int | None = None,
    *,
    timeout_seconds: int = 30,
    override_url: str | None = None,
    enable_failover: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
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
            response = requests.get(url, timeout=timeout_seconds)
            attempt["status_code"] = response.status_code
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("ESPN scoreboard payload must be a JSON object")

            attempt["status"] = "success"
            attempt["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
            attempts.append(attempt)

            diagnostics = {
                "mode": "live_fetch",
                "year": year,
                "week": week,
                "timeout_seconds": timeout_seconds,
                "urls_considered": urls,
                "attempts": attempts,
                "used_url": url,
                "failover_used": index > 1,
                "degraded": index > 1,
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
        "source": "espn",
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
    total_recalculated = 0
    for league_id in league_ids:
        for target_week in sorted(weeks):
            matchup_count = (
                db.query(models.Matchup)
                .filter(
                    models.Matchup.league_id == league_id,
                    models.Matchup.week == target_week,
                )
                .count()
            )
            if matchup_count == 0:
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

    db.commit()

    return {
        "leagues_touched": len({item["league_id"] for item in league_week_pairs}),
        "weeks_touched": len({item["week"] for item in league_week_pairs}),
        "matchups_recalculated": total_recalculated,
        "league_week_pairs": league_week_pairs,
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
        degraded = bool(fetch_diagnostics.get("degraded")) or len(inspection.missing_paths) > 0

        if dry_run:
            result = {
                "status": "success",
                "mode": "dry_run",
                "source": "espn",
                "year": year,
                "week": week,
                "fetched_events": inspection.event_count,
                "normalized_games": len(normalized.games),
                "normalized_player_rows": len(normalized.player_stats),
                "missing_required_paths_count": len(inspection.missing_paths),
                "missing_required_paths": inspection.missing_paths,
                "fetch_diagnostics": fetch_diagnostics,
                "degraded": degraded,
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
            result = {
                "status": "success",
                "mode": "apply",
                "source": "espn",
                "year": year,
                "week": week,
                **game_result,
                "player_stats": player_result,
                "reconciliation": reconcile_result,
                "fetch_diagnostics": fetch_diagnostics,
                "degraded": degraded,
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
            "source": "espn",
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
            "source": "espn",
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
