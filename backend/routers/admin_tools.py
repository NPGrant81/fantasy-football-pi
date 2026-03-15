# backend/routers/admin_tools.py
import os
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
# when running under the `backend` package we need the full path
# because the top-level `scripts` package is not on sys.path by default.
from backend.scripts.daily_sync import sync_nfl_reality
from ..core.security import check_is_commissioner

router = APIRouter(prefix="/admin/tools", tags=["Admin Tools"])

@router.post("/sync-nfl")
async def trigger_nfl_sync(background_tasks: BackgroundTasks, current_user=Depends(check_is_commissioner)):
    """
    Triggers the 'Daily Truth' sync script. 
    Runs in the background so it doesn't freeze your UI.
    """
    background_tasks.add_task(sync_nfl_reality)
    return {"message": "NFL Reality Sync started in the background!"}


from pydantic import BaseModel


class ScheduleImportPayload(BaseModel):
    year: int
    week: int | None = None


class LiveScoreIngestPayload(BaseModel):
    year: int
    week: int | None = None
    dry_run: bool = False
    timeout_seconds: int = 30
    override_url: str | None = None
    enable_failover: bool = True


class LiveScoreWatchdogPayload(BaseModel):
    limit: int = 20


@router.post("/import-nfl-schedule")
async def trigger_schedule_import(
    payload: ScheduleImportPayload,
    background_tasks: BackgroundTasks,
    current_user=Depends(check_is_commissioner),
):
    """
    Runs the NFL schedule importer for the given year (and optional week).
    This will hit ESPN and upsert rows into `nfl_games`.  The operation runs in
    a background task because the third-party API can be slow.

    Request body example:
    {
        "year": 2026,
        "week": 1   # optional
    }
    """
    # import lazily using the backend namespace for the same reason as
    # above (package context may differ between CLI scripts and uvicorn).
    from backend.scripts.import_nfl_schedule import upsert_games

    year = payload.year
    week = payload.week
    background_tasks.add_task(upsert_games, year, week)
    detail = f"Schedule import started for {year}"
    if week is not None:
        detail += f" week {week}"
    return {"detail": detail}


@router.post("/reload-config")
def reload_config(current_user=Depends(check_is_commissioner)):
    """Reload environment variables from the .env file.

    Call this after updating the file (or exporting new values) if you want the
    running process to pick them up without a restart.
    """
    # load the .env file from the project root (where the server was started).
    # using an explicit path makes the behavior deterministic for tests.
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.getcwd(), ".env")
    success = load_dotenv(dotenv_path=dotenv_path, override=True)
    return {"reloaded": bool(success)}


@router.post("/live-score-ingest")
def run_live_score_ingest(
    payload: LiveScoreIngestPayload,
    current_user=Depends(check_is_commissioner),
):
    """Run live scoring ingest with optional dry-run and failover/hot-fix controls.

    - `dry_run=true` fetches and validates payload without persisting DB changes.
    - `override_url` allows temporary hot-fix routing to a mirror endpoint.
    - `enable_failover=false` disables backup URLs for focused diagnostics.
    """
    from backend.services.live_scoring_ingest_service import IngestFetchError, run_live_scoreboard_ingest_with_controls

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


@router.get("/live-score-ingest/health")
def live_score_ingest_health(
    limit: int = Query(default=50, ge=1, le=500),
    current_user=Depends(check_is_commissioner),
):
    """Return ingest reliability summary from durable run-history logs."""
    from backend.services.live_scoring_ingest_service import summarize_ingest_health

    return summarize_ingest_health(limit=limit)


@router.post("/live-score-ingest/watchdog")
def run_live_score_ingest_watchdog(
    payload: LiveScoreWatchdogPayload,
    current_user=Depends(check_is_commissioner),
):
    """Run watchdog alert evaluation over recent ingest history."""
    from backend.services.live_scoring_watchdog_service import run_watchdog_check

    return run_watchdog_check(limit=payload.limit)


@router.get("/live-score-ingest/watchdog/alerts")
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
