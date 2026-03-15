from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:  # pragma: no cover - exercised implicitly via startup fallback
    BackgroundScheduler = None  # type: ignore[assignment]
    CronTrigger = None  # type: ignore[assignment]

from backend.services.live_scoring_ingest_service import summarize_ingest_health
from backend.services.notifications import NotifyService


LOGGER = logging.getLogger(__name__)
ALERT_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "ingest_health" / "live_scoring_watchdog_alerts.jsonl"
WATCHDOG_JOB_ID = "live_scoring_ingest_watchdog"
_scheduler: BackgroundScheduler | None = None


@dataclass(frozen=True)
class WatchdogThresholds:
    failure_rate: float = 0.5
    degraded_runs: int = 5
    repeated_error_count: int = 3
    limit: int = 20


def load_watchdog_thresholds_from_env() -> WatchdogThresholds:
    return WatchdogThresholds(
        failure_rate=float(os.getenv("LIVE_SCORING_WATCHDOG_FAILURE_RATE", "0.5")),
        degraded_runs=int(os.getenv("LIVE_SCORING_WATCHDOG_DEGRADED_RUNS", "5")),
        repeated_error_count=int(os.getenv("LIVE_SCORING_WATCHDOG_REPEATED_ERRORS", "3")),
        limit=int(os.getenv("LIVE_SCORING_WATCHDOG_LIMIT", "20")),
    )


def evaluate_watchdog_alerts(
    health_summary: dict[str, Any],
    *,
    thresholds: WatchdogThresholds,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    failure_rate = float(health_summary.get("failure_rate") or 0.0)
    degraded_runs = int(health_summary.get("degraded_runs") or 0)
    runs_considered = int(health_summary.get("runs_considered") or 0)
    top_errors = health_summary.get("top_error_signatures") or []

    if runs_considered == 0:
        return alerts

    if failure_rate >= thresholds.failure_rate:
        alerts.append(
            {
                "alert_type": "failure_rate",
                "severity": "high",
                "message": f"Live scoring ingest failure rate {failure_rate:.2%} exceeded threshold {thresholds.failure_rate:.2%}",
                "observed": failure_rate,
                "threshold": thresholds.failure_rate,
            }
        )

    if degraded_runs >= thresholds.degraded_runs:
        alerts.append(
            {
                "alert_type": "degraded_runs",
                "severity": "medium",
                "message": f"Live scoring ingest degraded runs {degraded_runs} exceeded threshold {thresholds.degraded_runs}",
                "observed": degraded_runs,
                "threshold": thresholds.degraded_runs,
            }
        )

    if top_errors:
        top = top_errors[0]
        count = int(top.get("count") or 0)
        if count >= thresholds.repeated_error_count:
            alerts.append(
                {
                    "alert_type": "repeated_error_signature",
                    "severity": "medium",
                    "message": (
                        f"Live scoring ingest error signature {top.get('error_signature')} "
                        f"recurred {count} times (threshold {thresholds.repeated_error_count})"
                    ),
                    "observed": count,
                    "threshold": thresholds.repeated_error_count,
                    "error_signature": top.get("error_signature"),
                }
            )

    return alerts


def _append_watchdog_alert_log(entry: dict[str, Any]) -> None:
    ALERT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ALERT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, default=str) + "\n")


def load_recent_watchdog_alerts(limit: int = 100) -> list[dict[str, Any]]:
    if limit <= 0 or not ALERT_LOG_PATH.exists():
        return []
    with ALERT_LOG_PATH.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
    rows: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        raw = line.strip()
        if not raw:
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return rows


def run_watchdog_check(
    *,
    limit: int | None = None,
    thresholds: WatchdogThresholds | None = None,
) -> dict[str, Any]:
    resolved_thresholds = thresholds or load_watchdog_thresholds_from_env()
    if limit is None:
        limit = resolved_thresholds.limit

    health_summary = summarize_ingest_health(limit=limit)
    alerts = evaluate_watchdog_alerts(health_summary, thresholds=resolved_thresholds)
    now = datetime.now(timezone.utc).isoformat()
    result = {
        "checked_at": now,
        "thresholds": {
            "failure_rate": resolved_thresholds.failure_rate,
            "degraded_runs": resolved_thresholds.degraded_runs,
            "repeated_error_count": resolved_thresholds.repeated_error_count,
            "limit": limit,
        },
        "health_summary": health_summary,
        "alert_count": len(alerts),
        "alerts": alerts,
    }

    if alerts:
        _append_watchdog_alert_log(result)
        _dispatch_watchdog_notifications(result)
        LOGGER.warning("live_scoring.watchdog_alert count=%s", len(alerts))
    else:
        LOGGER.info("live_scoring.watchdog_ok limit=%s", limit)

    return result


def _dispatch_watchdog_notifications(result: dict[str, Any]) -> None:
    raw_user_id = os.getenv("LIVE_SCORING_WATCHDOG_NOTIFY_USER_ID")
    if not raw_user_id:
        return
    try:
        user_id = int(raw_user_id)
    except ValueError:
        LOGGER.warning("live_scoring.watchdog_notify_invalid_user_id value=%s", raw_user_id)
        return

    NotifyService.send_transactional_email(
        user_id,
        "live_scoring_watchdog_alert",
        {
            "alert_count": result.get("alert_count", 0),
            "alerts": result.get("alerts", []),
            "checked_at": result.get("checked_at"),
            "health_summary": result.get("health_summary", {}),
        },
    )


def start_live_scoring_watchdog_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if BackgroundScheduler is None or CronTrigger is None:
        LOGGER.warning("live_scoring.watchdog_scheduler_unavailable reason=apscheduler_not_installed")
        return None
    if os.getenv("LIVE_SCORING_WATCHDOG_ENABLED", "0") != "1":
        return None
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    limit = int(os.getenv("LIVE_SCORING_WATCHDOG_LIMIT", "20"))
    schedule_mode = os.getenv("LIVE_SCORING_WATCHDOG_SCHEDULE_MODE", "cron").strip().lower()

    scheduler = BackgroundScheduler(timezone="UTC")

    if schedule_mode == "interval":
        interval_minutes = int(os.getenv("LIVE_SCORING_WATCHDOG_INTERVAL_MINUTES", "5"))
        scheduler.add_job(
            run_watchdog_check,
            "interval",
            minutes=interval_minutes,
            kwargs={"limit": limit},
            id=WATCHDOG_JOB_ID,
            replace_existing=True,
        )
        LOGGER.info(
            "live_scoring.watchdog_scheduler_started mode=interval interval_minutes=%s limit=%s",
            interval_minutes,
            limit,
        )
    else:
        cron_day = os.getenv("LIVE_SCORING_WATCHDOG_CRON_DAY_OF_WEEK", "sun")
        cron_hour = os.getenv("LIVE_SCORING_WATCHDOG_CRON_HOUR", "*")
        cron_minute = os.getenv("LIVE_SCORING_WATCHDOG_CRON_MINUTE", "*/5")
        scheduler.add_job(
            run_watchdog_check,
            CronTrigger(day_of_week=cron_day, hour=cron_hour, minute=cron_minute, timezone="UTC"),
            kwargs={"limit": limit},
            id=WATCHDOG_JOB_ID,
            replace_existing=True,
        )
        LOGGER.info(
            "live_scoring.watchdog_scheduler_started mode=cron day_of_week=%s hour=%s minute=%s limit=%s",
            cron_day,
            cron_hour,
            cron_minute,
            limit,
        )

    scheduler.start()
    _scheduler = scheduler
    return _scheduler


def stop_live_scoring_watchdog_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
