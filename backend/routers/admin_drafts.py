import logging
import os
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from ..core.security import check_is_commissioner

router = APIRouter(prefix="/admin/drafts", tags=["Admin Drafts"])


class RefreshDraftValuesPayload(BaseModel):
    season: int
    sources: list[str] = Field(default_factory=lambda: ["espn", "draftsharks"])
    espn_league_id: int | None = None
    espn_s2: str | None = None
    espn_swid: str | None = None
    include_yahoo: bool = False
    enforce_yahoo_precheck: bool = True
    yahoo_min_players: int = 50
    yahoo_min_adp_coverage: float = 0.80
    fantasynerds_api_key: str | None = None
    fantasynerds_teams: int = 12
    fantasynerds_budget: int = 200
    fantasynerds_format: str = "ppr"
    enforce_fantasynerds_precheck: bool = True
    fantasynerds_min_players: int = 150
    fantasynerds_min_auction_coverage: float = 0.80
    fantasynerds_min_minmax_coverage: float = 0.50


@router.post("/refresh-values")
def refresh_draft_values(
    payload: RefreshDraftValuesPayload,
    background_tasks: BackgroundTasks,
    current_user=Depends(check_is_commissioner),
):
    background_tasks.add_task(_run_draft_values_refresh, payload)
    return {
        "message": "Draft values refresh started in the background.",
        "season": payload.season,
        "sources": payload.sources,
    }


def _run_draft_values_refresh(payload: RefreshDraftValuesPayload) -> None:
    """
    Background task: extract -> load per-source -> aggregate consensus.
    Errors in individual sources are logged but do not abort the run so that
    one failing site cannot block the others.
    """
    logger = logging.getLogger("admin_drafts.refresh_draft_values")

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from backend.database import SessionLocal
    from etl.load.load_to_postgres import load_normalized_source_to_db

    season = payload.season
    sources = [s.lower() for s in payload.sources]
    results: dict[str, str] = {}

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

    if "fantasynerds" in sources:
        try:
            from etl.extract.extract_fantasynerds import (
                evaluate_fantasynerds_quality,
                fetch_fantasynerds_auction_values,
                transform_fantasynerds_auction_values,
            )

            api_key = payload.fantasynerds_api_key or os.getenv("FANTASYNERDS_API_KEY")
            if not api_key:
                raise ValueError("missing FantasyNerds API key")

            raw = fetch_fantasynerds_auction_values(
                api_key=api_key,
                teams=payload.fantasynerds_teams,
                budget=payload.fantasynerds_budget,
                scoring_format=payload.fantasynerds_format,
            )
            norm_df = transform_fantasynerds_auction_values(raw)

            if payload.enforce_fantasynerds_precheck:
                report = evaluate_fantasynerds_quality(
                    norm_df,
                    min_players=payload.fantasynerds_min_players,
                    min_auction_coverage=payload.fantasynerds_min_auction_coverage,
                    min_minmax_coverage=payload.fantasynerds_min_minmax_coverage,
                )
                if not report.passed:
                    results["fantasynerds"] = "blocked by precheck: " + "; ".join(report.errors)
                    logger.error(
                        "FantasyNerds precheck blocked load for season %d: %s",
                        season,
                        report.errors,
                    )
                    norm_df = None

            if norm_df is not None and not norm_df.empty:
                load_normalized_source_to_db(norm_df, season=season, source="FantasyNerds")
                results["fantasynerds"] = f"loaded {len(norm_df)} players"
                logger.info("FantasyNerds: loaded %d players for season %d", len(norm_df), season)
            elif "fantasynerds" not in results:
                results["fantasynerds"] = "no data returned"
                logger.warning("FantasyNerds: extractor returned no data")
        except Exception as exc:
            results["fantasynerds"] = f"error: {exc}"
            logger.exception("FantasyNerds extraction failed: %s", exc)

    if payload.include_yahoo:
        try:
            from etl.extract.extract_yahoo import fetch_yahoo_top_players, transform_yahoo_players

            players = fetch_yahoo_top_players(max_players=100)
            if players:
                import pandas as pd

                norm_df = pd.DataFrame(transform_yahoo_players(players))
                if payload.enforce_yahoo_precheck:
                    from etl.extract.extract_yahoo_precheck import evaluate_yahoo_quality

                    report = evaluate_yahoo_quality(
                        norm_df,
                        min_players=payload.yahoo_min_players,
                        min_adp_coverage=payload.yahoo_min_adp_coverage,
                    )
                    if not report.passed:
                        results["yahoo"] = "blocked by precheck: " + "; ".join(report.errors)
                        logger.error(
                            "Yahoo precheck blocked load for season %d: %s",
                            season,
                            report.errors,
                        )
                        norm_df = None
                if norm_df is not None and not norm_df.empty:
                    load_normalized_source_to_db(norm_df, season=season, source="Yahoo")
                    results["yahoo"] = f"loaded {len(norm_df)} players"
                    logger.info("Yahoo: loaded %d players for season %d", len(norm_df), season)
                elif "yahoo" not in results:
                    results["yahoo"] = "transform produced empty DataFrame"
            else:
                results["yahoo"] = "no data returned"
        except Exception as exc:
            results["yahoo"] = f"error: {exc}"
            logger.exception("Yahoo extraction failed: %s", exc)

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