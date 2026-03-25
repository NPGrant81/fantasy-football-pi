# backend/routers/admin_tools.py
import os
from pydantic import BaseModel
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


# ---------------------------------------------------------------------------
# Draft values refresh
# ---------------------------------------------------------------------------

class RefreshDraftValuesPayload(BaseModel):
    season: int
    sources: list[str] = ["espn", "draftsharks"]
    # Optional ESPN authenticated path (espn_api.football library).
    # If omitted, the public REST API is used instead.
    espn_league_id: int | None = None
    espn_s2: str | None = None
    espn_swid: str | None = None
    # Set True to also attempt Yahoo.
    # Credentials are read from YAHOO_CLIENT_ID / YAHOO_CLIENT_SECRET /
    # YAHOO_ACCESS_TOKEN / YAHOO_REFRESH_TOKEN env vars in backend/.env
    # (preferred), or from oauth2.json at the project root (legacy fallback).
    include_yahoo: bool = False


@router.post("/refresh-draft-values")
def refresh_draft_values(
    payload: RefreshDraftValuesPayload,
    background_tasks: BackgroundTasks,
    current_user=Depends(check_is_commissioner),
):
    """
    Pull external draft projection data (ESPN, DraftSharks, optionally Yahoo)
    into ``platform_projections``, then aggregate into ``draft_values`` so the
    Draft Day Analyzer has live consensus rankings.

    Runs in a background task.  Poll ``GET /admin/tools/refresh-draft-values/status``
    (not yet implemented) or check server logs for completion.

    Request body:
    ```json
    {
        "season": 2026,
        "sources": ["espn", "draftsharks"],
        "espn_league_id": null,
        "espn_s2": null,
        "espn_swid": null,
        "include_yahoo": false
    }
    ```

    ESPN credentials are only needed for the authenticated path (projected
    points).  Omit them to use the public auction-value endpoint instead.
    """
    background_tasks.add_task(_run_draft_values_refresh, payload)
    return {
        "message": "Draft values refresh started in the background.",
        "season": payload.season,
        "sources": payload.sources,
    }


def _run_draft_values_refresh(payload: RefreshDraftValuesPayload) -> None:
    """
    Background task: extract → load per-source → aggregate consensus.
    Errors in individual sources are logged but do not abort the run so that
    one failing site cannot block the others.
    """
    import logging
    import sys
    from pathlib import Path

    logger = logging.getLogger("admin_tools.refresh_draft_values")

    # Ensure the repo root is on sys.path so etl.* imports resolve correctly
    # when this background task runs inside the uvicorn process.
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from backend.database import SessionLocal
    from etl.load.load_to_postgres import load_normalized_source_to_db

    season = payload.season
    sources = [s.lower() for s in payload.sources]
    results: dict[str, str] = {}

    # ── ESPN ─────────────────────────────────────────────────────────────
    if "espn" in sources:
        try:
            if payload.espn_league_id and payload.espn_s2 and payload.espn_swid:
                from etl.extract.extract_espn import fetch_espn_top300_with_auth
                norm_df = fetch_espn_top300_with_auth(
                    year=season,
                    league_id=payload.espn_league_id,
                    espn_s2=payload.espn_s2,
                    swid=payload.espn_swid,
                )
                source_label = "ESPN"
            else:
                from etl.extract.extract_espn import scrape_espn_top_300, transform_espn_top_300
                raw = scrape_espn_top_300(season=season, is_ppr=True)
                norm_df = transform_espn_top_300(raw) if raw is not None else None
                source_label = "ESPN"

            if norm_df is not None and not norm_df.empty:
                load_normalized_source_to_db(norm_df, season=season, source=source_label)
                results["espn"] = f"loaded {len(norm_df)} players"
                logger.info("ESPN: loaded %d players for season %d", len(norm_df), season)
            else:
                results["espn"] = "no data returned"
                logger.warning("ESPN: extractor returned no data for season %d", season)
        except Exception as exc:
            results["espn"] = f"error: {exc}"
            logger.exception("ESPN extraction failed: %s", exc)

    # ── DraftSharks ──────────────────────────────────────────────────────
    if "draftsharks" in sources:
        try:
            from etl.extract.extract_draftsharks import (
                scrape_draft_sharks_auction_values,
                transform_draftsharks_auction_values,
            )
            raw = scrape_draft_sharks_auction_values()
            if raw is not None and not raw.empty:
                norm_df = transform_draftsharks_auction_values(raw)
                if not norm_df.empty:
                    load_normalized_source_to_db(norm_df, season=season, source="DraftSharks")
                    results["draftsharks"] = f"loaded {len(norm_df)} players"
                    logger.info("DraftSharks: loaded %d players for season %d", len(norm_df), season)
                else:
                    results["draftsharks"] = "transform produced empty DataFrame"
            else:
                results["draftsharks"] = "no data returned"
                logger.warning("DraftSharks: scraper returned no data")
        except Exception as exc:
            results["draftsharks"] = f"error: {exc}"
            logger.exception("DraftSharks extraction failed: %s", exc)

    # ── Yahoo (optional) ─────────────────────────────────────────────────
    if payload.include_yahoo:
        try:
            from etl.extract.extract_yahoo import fetch_yahoo_top_players, transform_yahoo_players
            players = fetch_yahoo_top_players(max_players=100)
            if players:
                import pandas as pd
                norm_df = pd.DataFrame(transform_yahoo_players(players))
                if not norm_df.empty:
                    load_normalized_source_to_db(norm_df, season=season, source="Yahoo")
                    results["yahoo"] = f"loaded {len(norm_df)} players"
                    logger.info("Yahoo: loaded %d players for season %d", len(norm_df), season)
                else:
                    results["yahoo"] = "transform produced empty DataFrame"
            else:
                results["yahoo"] = "no data returned"
        except Exception as exc:
            results["yahoo"] = f"error: {exc}"
            logger.exception("Yahoo extraction failed: %s", exc)

    # ── Aggregate into draft_values ───────────────────────────────────────
    try:
        from etl.services.consensus_service import build_and_store_consensus_draft_values
        db = SessionLocal()
        try:
            summary = build_and_store_consensus_draft_values(db, season=season)
            results["consensus"] = f"updated {summary.get('updated', 0)} draft_values rows"
            logger.info(
                "Consensus aggregation complete: %d updated, sources=%s",
                summary.get("updated", 0),
                summary.get("sources_seen", []),
            )
        finally:
            db.close()
    except Exception as exc:
        results["consensus"] = f"error: {exc}"
        logger.exception("Consensus aggregation failed: %s", exc)

    logger.info("Draft values refresh complete — season=%d results=%s", season, results)
