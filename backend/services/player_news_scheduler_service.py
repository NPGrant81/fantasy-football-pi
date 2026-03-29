from __future__ import annotations

import logging
import os

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover
    BackgroundScheduler = None  # type: ignore[assignment]

from backend import models
from backend.database import SessionLocal
from backend.services.player_news_service import run_ingest_for_league


LOGGER = logging.getLogger(__name__)
NEWS_INGEST_JOB_ID = "player_news_ingest"
_scheduler: BackgroundScheduler | None = None


def run_player_news_ingest_cycle() -> dict[str, int]:
    db = SessionLocal()
    leagues_processed = 0
    inserted_total = 0
    linked_total = 0
    skipped_total = 0

    try:
        league_ids = [row[0] for row in db.query(models.League.id).all()]
        include_external_sources = os.getenv("PLAYER_NEWS_INCLUDE_EXTERNAL", "0") == "1"

        for league_id in league_ids:
            summary = run_ingest_for_league(
                db,
                league_id=league_id,
                include_draft_activity=True,
                include_external_sources=include_external_sources,
            )
            leagues_processed += 1
            inserted_total += summary.inserted
            linked_total += summary.linked
            skipped_total += summary.skipped

        result = {
            "leagues_processed": leagues_processed,
            "inserted": inserted_total,
            "linked": linked_total,
            "skipped": skipped_total,
        }
        LOGGER.info("player_news.ingest_cycle", extra=result)
        return result
    finally:
        db.close()


def start_player_news_ingest_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if BackgroundScheduler is None:
        LOGGER.warning("player_news.scheduler_unavailable reason=apscheduler_not_installed")
        return None
    if os.getenv("PLAYER_NEWS_INGEST_ENABLED", "0") != "1":
        return None
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    interval_minutes = int(os.getenv("PLAYER_NEWS_INGEST_INTERVAL_MINUTES", "30"))

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_player_news_ingest_cycle,
        "interval",
        minutes=interval_minutes,
        id=NEWS_INGEST_JOB_ID,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler

    LOGGER.info(
        "player_news.scheduler_started interval_minutes=%s",
        interval_minutes,
    )
    return _scheduler


def stop_player_news_ingest_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
