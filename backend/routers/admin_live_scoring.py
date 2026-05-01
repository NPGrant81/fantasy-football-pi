from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..core.security import check_is_commissioner

router = APIRouter(prefix="/admin/live-scoring", tags=["Admin Live Scoring"])


class LiveScoreIngestPayload(BaseModel):
    year: int
    week: int | None = None
    dry_run: bool = False
    timeout_seconds: int = 30
    override_url: str | None = None
    enable_failover: bool = True


class LiveScoreWatchdogPayload(BaseModel):
    limit: int = 20


@router.post("/ingest")
def run_live_score_ingest(
    payload: LiveScoreIngestPayload,
    current_user=Depends(check_is_commissioner),
):
    """Run live scoring ingest with optional dry-run and failover controls."""
    from backend.services.live_scoring_ingest_service import (
        IngestFetchError,
        run_live_scoreboard_ingest_with_controls,
    )

    try:
        return run_live_scoreboard_ingest_with_controls(
            year=payload.year,
            week=payload.week,
            dry_run=payload.dry_run,
            timeout_seconds=payload.timeout_seconds,
            override_url=payload.override_url,
            enable_failover=payload.enable_failover,
        )
    except IngestFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": str(exc),
                "error_signature": type(exc).__name__,
                "fetch_diagnostics": exc.diagnostics,
            },
        ) from exc


@router.get("/health")
def live_score_ingest_health(
    limit: int = Query(default=50, ge=1, le=500),
    current_user=Depends(check_is_commissioner),
):
    """Return ingest reliability summary from durable run-history logs."""
    from backend.services.live_scoring_ingest_service import summarize_ingest_health

    return summarize_ingest_health(limit=limit)


@router.post("/watchdog")
def run_live_score_ingest_watchdog(
    payload: LiveScoreWatchdogPayload,
    current_user=Depends(check_is_commissioner),
):
    """Run watchdog alert evaluation over recent ingest history."""
    from backend.services.live_scoring_watchdog_service import run_watchdog_check

    return run_watchdog_check(limit=payload.limit)


@router.get("/watchdog/alerts")
def live_score_watchdog_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    current_user=Depends(check_is_commissioner),
):
    """Return recent watchdog alert records from durable alert logs."""
    from backend.services.live_scoring_watchdog_service import load_recent_watchdog_alerts

    return {
        "alerts": load_recent_watchdog_alerts(limit=limit),
        "limit": limit,
    }