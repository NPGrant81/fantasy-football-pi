from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover
    BackgroundScheduler = None  # type: ignore[assignment]

from backend.services.live_scoring_ingest_service import run_live_scoreboard_ingest_with_controls


LOGGER = logging.getLogger(__name__)
POLL_JOB_ID = "live_scoring_polling"
ACTIVE_PHASES = {"live", "halftime"}
CYCLE_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "ingest_health" / "live_scoring_poll_cycles.jsonl"
_scheduler: BackgroundScheduler | None = None
_runtime_lock = threading.Lock()
_RUNTIME_STATE: dict[str, dict[str, Any]] = {}


def _append_poll_cycle_log(entry: dict[str, Any]) -> None:
    CYCLE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CYCLE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, default=str) + "\n")


def load_recent_poll_cycles(limit: int = 100) -> list[dict[str, Any]]:
    if limit <= 0 or not CYCLE_LOG_PATH.exists():
        return []
    with CYCLE_LOG_PATH.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
    rows: list[dict[str, Any]] = []
    for raw in lines[-limit:]:
        line = raw.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def summarize_poll_cycles(limit: int = 100) -> dict[str, Any]:
    cycles = load_recent_poll_cycles(limit=limit)
    status_counts = {"success": 0, "skipped": 0, "failed": 0}
    mode_counts: dict[str, int] = {}

    for item in cycles:
        status = str(item.get("status") or "unknown")
        if status in status_counts:
            status_counts[status] += 1

        mode = item.get("mode")
        if mode:
            mode_key = str(mode)
            mode_counts[mode_key] = mode_counts.get(mode_key, 0) + 1

    return {
        "cycles_considered": len(cycles),
        "status_counts": status_counts,
        "mode_counts": mode_counts,
        "last_cycle": cycles[-1] if cycles else None,
        "cycles": cycles,
    }


def get_poll_runtime_status() -> dict[str, Any]:
    with _runtime_lock:
        runtime = json.loads(json.dumps(_RUNTIME_STATE, default=str))
    return {
        "scheduler_running": bool(_scheduler and _scheduler.running),
        "keys": sorted(runtime.keys()),
        "state": runtime,
    }


def _active_interval_seconds() -> int:
    return max(15, int(os.getenv("LIVE_SCORING_POLL_ACTIVE_INTERVAL_SECONDS", "20")))


def _idle_interval_seconds() -> int:
    return max(30, int(os.getenv("LIVE_SCORING_POLL_IDLE_INTERVAL_SECONDS", "90")))


def _poll_tick_seconds() -> int:
    return max(5, int(os.getenv("LIVE_SCORING_POLL_TICK_SECONDS", "15")))


def _default_year() -> int:
    return int(os.getenv("LIVE_SCORING_POLL_YEAR", str(datetime.now(timezone.utc).year)))


def _default_week() -> int | None:
    raw = os.getenv("LIVE_SCORING_POLL_WEEK")
    if not raw:
        return None
    return int(raw)


def _detect_state_transitions(previous: dict[str, str], current: dict[str, str]) -> list[dict[str, str]]:
    transitions: list[dict[str, str]] = []
    for event_id in sorted(set(previous) | set(current)):
        from_state = previous.get(event_id)
        to_state = current.get(event_id)
        if from_state == to_state:
            continue
        transitions.append(
            {
                "event_id": event_id,
                "from": from_state or "unknown",
                "to": to_state or "unknown",
            }
        )
    return transitions


def _has_active_games(game_states: dict[str, str]) -> bool:
    return any(state in ACTIVE_PHASES for state in game_states.values())


def run_live_scoring_poll_cycle(
    *,
    year: int | None = None,
    week: int | None = None,
) -> dict[str, Any]:
    target_year = year if year is not None else _default_year()
    target_week = week if week is not None else _default_week()
    key = f"{target_year}:{target_week if target_week is not None else 'all'}"
    cycle_started_at = datetime.now(timezone.utc).isoformat()

    active_interval = _active_interval_seconds()
    idle_interval = _idle_interval_seconds()
    now_epoch = time.time()

    with _runtime_lock:
        previous_state = _RUNTIME_STATE.get(key, {})
        previous_game_states = dict(previous_state.get("game_states") or {})
        previous_fingerprint = previous_state.get("fingerprint")
        last_polled_epoch = float(previous_state.get("last_polled_epoch") or 0.0)
        previous_active = _has_active_games(previous_game_states)

    required_interval = active_interval if previous_active else idle_interval
    elapsed = now_epoch - last_polled_epoch
    if last_polled_epoch > 0 and elapsed < required_interval:
        result = {
            "status": "skipped",
            "reason": "interval_gate",
            "year": target_year,
            "week": target_week,
            "cycle_started_at": cycle_started_at,
            "required_interval_seconds": required_interval,
            "elapsed_seconds": round(elapsed, 2),
            "active_games": sum(1 for value in previous_game_states.values() if value in ACTIVE_PHASES),
            "downstream_updates_triggered": False,
        }
        _append_poll_cycle_log(result)
        return result

    inspect_event_contracts_enabled = os.getenv("LIVE_SCORING_POLL_INSPECT_EVENT_CONTRACTS", "0") == "1"
    event_contracts_limit = int(os.getenv("LIVE_SCORING_POLL_EVENT_CONTRACTS_LIMIT", "1"))
    timeout_seconds = int(os.getenv("LIVE_SCORING_POLL_TIMEOUT_SECONDS", "20"))
    enable_failover = os.getenv("LIVE_SCORING_POLL_ENABLE_FAILOVER", "1") == "1"

    try:
        ingest_result = run_live_scoreboard_ingest_with_controls(
            year=target_year,
            week=target_week,
            dry_run=False,
            timeout_seconds=timeout_seconds,
            enable_failover=enable_failover,
            inspect_event_contracts_enabled=inspect_event_contracts_enabled,
            event_contracts_limit=event_contracts_limit,
            change_guard_fingerprint=previous_fingerprint,
        )
    except Exception as exc:  # noqa: BLE001
        failure = {
            "status": "failed",
            "year": target_year,
            "week": target_week,
            "cycle_started_at": cycle_started_at,
            "error": str(exc),
            "error_signature": type(exc).__name__,
            "downstream_updates_triggered": False,
        }
        with _runtime_lock:
            record = _RUNTIME_STATE.setdefault(key, {})
            record["last_polled_epoch"] = now_epoch
            record["last_error"] = failure
            record["last_result"] = failure
        _append_poll_cycle_log(failure)
        LOGGER.warning(
            "live_scoring.poll_cycle_failed year=%s week=%s signature=%s",
            target_year,
            target_week,
            failure["error_signature"],
        )
        return failure

    game_states = dict(ingest_result.get("game_states") or {})
    transitions = _detect_state_transitions(previous_game_states, game_states)
    active_games = sum(1 for value in game_states.values() if value in ACTIVE_PHASES)
    is_active_window = active_games > 0
    next_interval_seconds = active_interval if is_active_window else idle_interval

    with _runtime_lock:
        record = _RUNTIME_STATE.setdefault(key, {})
        record["fingerprint"] = ingest_result.get("scoreboard_fingerprint")
        record["game_states"] = game_states
        record["last_polled_epoch"] = now_epoch
        record["last_mode"] = ingest_result.get("mode")
        record["last_error"] = None
        if ingest_result.get("downstream_updates_triggered"):
            record["last_apply_epoch"] = now_epoch

    result = {
        "status": "success",
        "year": target_year,
        "week": target_week,
        "cycle_started_at": cycle_started_at,
        "mode": ingest_result.get("mode"),
        "active_games": active_games,
        "is_active_window": is_active_window,
        "state_transitions": transitions,
        "scoreboard_fingerprint": ingest_result.get("scoreboard_fingerprint"),
        "change_detected": bool(ingest_result.get("change_detected", True)),
        "downstream_updates_triggered": bool(ingest_result.get("downstream_updates_triggered", False)),
        "next_interval_seconds": next_interval_seconds,
        "ingest": ingest_result,
    }
    with _runtime_lock:
        record = _RUNTIME_STATE.setdefault(key, {})
        record["last_result"] = result
    _append_poll_cycle_log(result)

    # Push a real-time event to connected SSE clients when scoring changed.
    if result["downstream_updates_triggered"]:
        try:
            from backend.services.live_scoring_event_bus import (
                build_score_update_event,
                publish_from_thread,
            )

            event = build_score_update_event(
                year=target_year,
                week=target_week,
                active_games=active_games,
                is_active_window=is_active_window,
                state_transitions=transitions,
                scoreboard_fingerprint=ingest_result.get("scoreboard_fingerprint"),
                matchup_projection_snapshots=ingest_result.get("matchup_projection_snapshots"),
            )
            publish_from_thread(event)
        except Exception as _bus_exc:  # pragma: no cover
            LOGGER.debug("live_scoring.poll_cycle event_bus_publish_failed err=%s", _bus_exc)

    LOGGER.info(
        "live_scoring.poll_cycle mode=%s active_games=%s transitions=%s downstream_updates=%s",
        result["mode"],
        active_games,
        len(transitions),
        result["downstream_updates_triggered"],
    )
    return result


def start_live_scoring_polling_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if BackgroundScheduler is None:
        LOGGER.warning("live_scoring.polling_scheduler_unavailable reason=apscheduler_not_installed")
        return None
    if os.getenv("LIVE_SCORING_POLLING_ENABLED", "0") != "1":
        return None
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler(timezone="UTC")
    tick_seconds = _poll_tick_seconds()
    scheduler.add_job(
        run_live_scoring_poll_cycle,
        "interval",
        seconds=tick_seconds,
        id=POLL_JOB_ID,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    LOGGER.info("live_scoring.polling_scheduler_started tick_seconds=%s", tick_seconds)
    return _scheduler


def stop_live_scoring_polling_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
