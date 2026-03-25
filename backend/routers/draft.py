from typing import Any, List
from datetime import datetime, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
import pandas as pd
from sqlalchemy import func, distinct, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

# Internal Imports
from ..database import get_db
import models
import models_draft_value
from ..schemas.draft import HistoricalRankingResponse
from ..services.ledger_service import owner_draft_budget_total, owner_has_incoming_credits
from ..services.player_service import normalize_display_name as _normalize_player_name
from ..services.draft_rankings_service import get_historical_rankings as get_historical_rankings_service
from ..core.security import get_current_user
from ..services.validation_service import (
    validate_draft_pick_boundary,
    validate_draft_pick_dynamic_rules,
)
from etl.transform.monte_carlo_simulation import (
    SimulationConfig,
    key_target_probabilities,
    run_monte_carlo_draft_simulation,
    run_monte_carlo_from_paths,
    summarize_team_distribution,
)

# Create the router
# Note: We removed the 'prefix' so your current frontend links (/draft-history) 
# don't break. We can add /draft prefix later when we update the frontend.
router = APIRouter(tags=["Draft"])
logger = logging.getLogger(__name__)

# --- 1. WEBSOCKET CONNECTION MANAGER (KEEP THIS!) ---
# This handles the "Real Time" part (pushing updates to all owners instantly)
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()


def _parse_session_context(session_id: str) -> tuple[int | None, int | None]:
    league_id = None
    draft_year = None
    parts = (session_id or "").split("_")
    for idx, value in enumerate(parts):
        if value == "LEAGUE" and idx + 1 < len(parts):
            try:
                league_id = int(parts[idx + 1])
            except ValueError:
                league_id = None
        if value == "YEAR" and idx + 1 < len(parts):
            try:
                draft_year = int(parts[idx + 1])
            except ValueError:
                draft_year = None
    return league_id, draft_year


def _get_league_settings(db: Session, league_id: int | None):
    if not league_id:
        return None
    return (
        db.query(models.LeagueSettings)
        .filter(models.LeagueSettings.league_id == league_id)
        .first()
    )


def _get_owner_total_budget(
    db: Session,
    *,
    league_id: int | None,
    owner_id: int,
    draft_year: int,
) -> int:
    if league_id and owner_has_incoming_credits(
        db,
        league_id=league_id,
        owner_id=owner_id,
        currency_type="DRAFT_DOLLARS",
        season_year=draft_year,
    ):
        return owner_draft_budget_total(
            db,
            league_id=league_id,
            owner_id=owner_id,
            season_year=draft_year,
            include_keeper_locks=False,
        )

    budget_row = (
        db.query(models.DraftBudget)
        .filter(
            models.DraftBudget.owner_id == owner_id,
            models.DraftBudget.year == draft_year,
            models.DraftBudget.league_id == league_id,
        )
        .first()
    )
    if budget_row and budget_row.total_budget is not None:
        return int(budget_row.total_budget)

    settings = _get_league_settings(db, league_id)
    if settings and settings.salary_cap is not None:
        return int(settings.salary_cap)
    return 200


def _get_keeper_carryover_rows(db: Session, *, league_id: int | None, draft_year: int):
    if not league_id or not draft_year:
        return []
    prior_year = draft_year - 1
    return (
        db.query(models.Keeper)
        .filter(
            models.Keeper.league_id == league_id,
            models.Keeper.season == prior_year,
            or_(
                models.Keeper.status == "locked",
                models.Keeper.approved_by_commish.is_(True),
            ),
        )
        .all()
    )


def _get_enriched_history(session_id: str, db: Session):
    picks = (
        db.query(models.DraftPick)
        .filter(models.DraftPick.session_id == session_id)
        .all()
    )

    league_id, parsed_year = _parse_session_context(session_id)
    keepers = _get_keeper_carryover_rows(db, league_id=league_id, draft_year=parsed_year)

    return _serialize_draft_events(picks=picks, keepers=keepers)


def _serialize_draft_events(
    *,
    picks: list[models.DraftPick],
    keepers: list[models.Keeper],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for pick in picks:
        events.append(
            {
                "id": pick.id,
                "owner_id": pick.owner_id,
                "player_id": pick.player_id,
                "amount": pick.amount,
                "timestamp": pick.timestamp,
                "position": pick.player.position if pick.player else None,
                "player_name": _normalize_player_name(pick.player.name) if pick.player else None,
                "is_keeper": False,
            }
        )

    for keeper in keepers:
        events.append(
            {
                "id": f"keeper-{keeper.id}",
                "owner_id": keeper.owner_id,
                "player_id": keeper.player_id,
                "amount": int(keeper.keep_cost or 0),
                "timestamp": (
                    keeper.created_at.isoformat()
                    if keeper.created_at is not None
                    else None
                ),
                "position": keeper.player.position if keeper.player else None,
                "player_name": _normalize_player_name(keeper.player.name) if keeper.player else None,
                "is_keeper": True,
            }
        )

    return events

# --- 2. SCHEMAS (Moved from main.py) ---
class DraftPickCreate(BaseModel):
    owner_id: int
    player_id: int 
    amount: int
    session_id: str
    year: int | None = None


class FocalOwnerStrategyKnobs(BaseModel):
    aggressiveness_multiplier: float = 1.0
    position_weights: dict[str, float] | None = None
    risk_tolerance: float = 0.5
    player_reliability_weight: float = 1.0


class DraftSimulationRequest(BaseModel):
    perspective_owner_id: int | None = None
    iterations: int = 500
    seed: int = 42
    teams_count: int = 12
    roster_size: int = 16
    target_key_players: int = 15
    yearly_results_path: str | None = None
    strategy: FocalOwnerStrategyKnobs = FocalOwnerStrategyKnobs()


class ModelServingLeagueConfig(BaseModel):
    teams_count: int | None = None
    roster_size: int | None = None
    salary_cap: int | None = None
    position_weights: dict[str, float] | None = None


class ModelServingDraftState(BaseModel):
    drafted_player_ids: list[int] = Field(default_factory=list)
    remaining_budget_by_owner: dict[int, float] | None = None
    remaining_slots_by_owner: dict[int, int] | None = None


class ModelServingPredictionRequest(BaseModel):
    owner_id: int
    season: int
    league_id: int | None = None
    player_ids: list[int] | None = None
    limit: int = 75
    model_version: str | None = "current"
    league_config: ModelServingLeagueConfig | None = None
    draft_state: ModelServingDraftState | None = None


class ModelServingRecommendation(BaseModel):
    player_id: int
    player_name: str
    position: str | None = None
    value_score: float
    recommended_bid: float
    predicted_value: float
    tier: str | None = None
    risk_score: float
    within_owner_budget: bool
    flags: list[str] = Field(default_factory=list)


class ModelServingPredictionResponse(BaseModel):
    api_version: str
    model_version_requested: str
    model_version_resolved: str
    generated_at: str
    owner_id: int
    season: int
    league_id: int | None = None
    recommendation_count: int
    recommendations: list[ModelServingRecommendation]


def _resolve_model_version(requested_version: str | None) -> str:
    requested = (requested_version or "current").strip().lower()
    if requested in {"", "current", "latest", "default"}:
        return "historical-rankings-v1"
    return requested_version or "historical-rankings-v1"


def _build_model_recommendations(
    rows: list[dict[str, Any]],
    *,
    owner_budget_remaining: float | None,
    owner_slots_remaining: int | None,
) -> list[dict[str, Any]]:
    max_owner_bid: float | None = None
    if owner_budget_remaining is not None and owner_slots_remaining is not None:
        safe_slots = max(int(owner_slots_remaining), 1)
        max_owner_bid = max(float(owner_budget_remaining) - float(safe_slots - 1), 1.0)

    recommendations: list[dict[str, Any]] = []
    for row in rows:
        predicted_value = float(row.get("predicted_auction_value") or 0.0)
        value_score = float(row.get("final_score") or 0.0)

        reliability_blend = (
            float(row.get("scoring_consistency_factor") or 1.0)
            * float(row.get("late_start_consistency_factor") or 1.0)
            * float(row.get("injury_split_factor") or 1.0)
            * float(row.get("team_change_factor") or 1.0)
        )
        risk_score = max(0.0, min(100.0, (1.0 - min(max(reliability_blend, 0.0), 1.5) / 1.5) * 100.0))

        recommended_bid = max(1.0, predicted_value)
        within_owner_budget = True
        if max_owner_bid is not None:
            if recommended_bid > max_owner_bid:
                recommended_bid = max_owner_bid
                within_owner_budget = False

        flags: list[str] = []
        if risk_score >= 65:
            flags.append("high-risk")
        if float(row.get("keeper_scarcity_boost") or 1.0) >= 1.15:
            flags.append("scarcity-boost")
        if not within_owner_budget:
            flags.append("budget-capped")

        recommendations.append(
            {
                "player_id": int(row.get("player_id") or 0),
                "player_name": str(row.get("player_name") or "Unknown"),
                "position": row.get("position"),
                "value_score": value_score,
                "recommended_bid": float(round(recommended_bid, 2)),
                "predicted_value": float(round(predicted_value, 2)),
                "tier": row.get("consensus_tier"),
                "risk_score": float(round(risk_score, 2)),
                "within_owner_budget": within_owner_budget,
                "flags": flags,
            }
        )

    return recommendations

# --- 3. STANDARD ENDPOINTS (From main.py - The ones working NOW) ---


# Existing endpoint
@router.get("/draft-history")
def get_draft_history(session_id: str, db: Session = Depends(get_db)):
    return _get_enriched_history(session_id=session_id, db=db)

# --- NEW: GET /draft/history (alias for /draft-history) ---
@router.get("/draft/history")
def get_draft_history_alias(session_id: str, db: Session = Depends(get_db)):
    return _get_enriched_history(session_id=session_id, db=db)


@router.get("/draft/seasons", response_model=list[int])
def get_draft_seasons(
    league_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.league_id:
        raise HTTPException(status_code=400, detail="User must belong to a league")

    target_league_id = int(league_id) if league_id is not None else int(current_user.league_id)
    if target_league_id != int(current_user.league_id):
        raise HTTPException(status_code=403, detail="Cross-league season queries are not allowed")

    years = [
        int(row[0])
        for row in (
            db.query(models.DraftPick.year)
            .filter(
                models.DraftPick.league_id == target_league_id,
                models.DraftPick.year.isnot(None),
            )
            .distinct()
            .order_by(models.DraftPick.year.desc())
            .all()
        )
        if row[0] is not None
    ]

    settings = _get_league_settings(db, target_league_id)
    if settings and settings.draft_year is not None and int(settings.draft_year) not in years:
        years.append(int(settings.draft_year))

    return sorted(set(years), reverse=True)


@router.get("/draft/history/by-year")
def get_draft_history_by_year(
    year: int,
    league_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.league_id:
        raise HTTPException(status_code=400, detail="User must belong to a league")

    target_league_id = int(league_id) if league_id is not None else int(current_user.league_id)
    if target_league_id != int(current_user.league_id):
        raise HTTPException(status_code=403, detail="Cross-league history queries are not allowed")

    picks = (
        db.query(models.DraftPick)
        .filter(
            models.DraftPick.league_id == target_league_id,
            models.DraftPick.year == year,
        )
        .all()
    )
    keepers = _get_keeper_carryover_rows(db, league_id=target_league_id, draft_year=year)
    return _serialize_draft_events(picks=picks, keepers=keepers)


@router.get("/draft/rankings", response_model=List[HistoricalRankingResponse])
def get_historical_rankings(
    season: int,
    limit: int = 40,
    league_id: int | None = None,
    owner_id: int | None = None,
    position: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.league_id:
        raise HTTPException(status_code=400, detail="User must belong to a league")

    requested_league_id = league_id if league_id is not None else current_user.league_id
    if int(requested_league_id) != int(current_user.league_id):
        raise HTTPException(status_code=403, detail="Cross-league ranking requests are not allowed")

    if owner_id is not None:
        if not current_user.is_superuser and not current_user.is_commissioner and int(owner_id) != int(current_user.id):
            raise HTTPException(
                status_code=403,
                detail="Owners can only request rankings for themselves",
            )
        target_owner = (
            db.query(models.User)
            .filter(
                models.User.id == owner_id,
                models.User.league_id == current_user.league_id,
            )
            .first()
        )
        if not target_owner:
            raise HTTPException(status_code=404, detail="Owner not found in league")

    return get_historical_rankings_service(
        db,
        season=season,
        limit=limit,
        league_id=requested_league_id,
        owner_id=owner_id,
        position=position,
    )


@router.post("/draft/model/predict", response_model=ModelServingPredictionResponse)
def predict_model_recommendations(
    payload: ModelServingPredictionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.league_id:
        raise HTTPException(status_code=400, detail="User must belong to a league")

    target_owner = (
        db.query(models.User)
        .filter(
            models.User.id == payload.owner_id,
            models.User.league_id == current_user.league_id,
        )
        .first()
    )
    if not target_owner:
        raise HTTPException(status_code=404, detail="Owner not found in league")

    if not current_user.is_superuser and not current_user.is_commissioner and int(payload.owner_id) != int(current_user.id):
        raise HTTPException(
            status_code=403,
            detail="Owners can only request model recommendations for themselves",
        )

    requested_league_id = payload.league_id if payload.league_id is not None else current_user.league_id
    if int(requested_league_id) != int(current_user.league_id):
        raise HTTPException(status_code=403, detail="Cross-league prediction requests are not allowed")

    resolved_model_version = _resolve_model_version(payload.model_version)
    safe_limit = max(1, min(int(payload.limit), 200))

    logger.info(
        "model_predict.request owner_id=%s season=%s league_id=%s model_version=%s limit=%s",
        payload.owner_id,
        payload.season,
        requested_league_id,
        resolved_model_version,
        safe_limit,
    )

    ranking_rows = get_historical_rankings_service(
        db,
        season=int(payload.season),
        limit=max(safe_limit * 2, 100),
        league_id=int(requested_league_id),
        owner_id=int(payload.owner_id),
        position=None,
    )

    drafted_ids = set(int(player_id) for player_id in (payload.draft_state.drafted_player_ids if payload.draft_state else []))
    candidate_rows = [
        row
        for row in ranking_rows
        if int(row.get("player_id") or 0) not in drafted_ids
    ]

    if payload.player_ids:
        allowed_ids = set(int(player_id) for player_id in payload.player_ids)
        candidate_rows = [
            row for row in candidate_rows if int(row.get("player_id") or 0) in allowed_ids
        ]

    owner_budget_remaining: float | None = None
    owner_slots_remaining: int | None = None
    if payload.draft_state and payload.draft_state.remaining_budget_by_owner:
        owner_budget_remaining = payload.draft_state.remaining_budget_by_owner.get(int(payload.owner_id))
    if payload.draft_state and payload.draft_state.remaining_slots_by_owner:
        owner_slots_remaining = payload.draft_state.remaining_slots_by_owner.get(int(payload.owner_id))

    recommendations = _build_model_recommendations(
        candidate_rows[:safe_limit],
        owner_budget_remaining=owner_budget_remaining,
        owner_slots_remaining=owner_slots_remaining,
    )

    logger.info(
        "model_predict.response owner_id=%s season=%s recommendation_count=%s",
        payload.owner_id,
        payload.season,
        len(recommendations),
    )

    return ModelServingPredictionResponse(
        api_version="v1",
        model_version_requested=payload.model_version or "current",
        model_version_resolved=resolved_model_version,
        generated_at=datetime.now(timezone.utc).isoformat(),
        owner_id=int(payload.owner_id),
        season=int(payload.season),
        league_id=int(requested_league_id),
        recommendation_count=len(recommendations),
        recommendations=[ModelServingRecommendation(**row) for row in recommendations],
    )


@router.post("/draft/simulation")
def run_draft_simulation(
    payload: DraftSimulationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    logger.info(
        "draft_simulation.request user_id=%s perspective_owner_id=%s iterations=%s teams_count=%s",
        current_user.id,
        payload.perspective_owner_id,
        payload.iterations,
        payload.teams_count,
    )

    if not current_user.league_id:
        raise HTTPException(status_code=400, detail="User must belong to a league")

    perspective_owner_id = int(payload.perspective_owner_id or current_user.id)
    if not current_user.is_superuser and not current_user.is_commissioner and perspective_owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Owners can only run perspective simulations for themselves",
        )

    perspective_owner = (
        db.query(models.User)
        .filter(
            models.User.id == perspective_owner_id,
            models.User.league_id == current_user.league_id,
        )
        .first()
    )
    if not perspective_owner:
        raise HTTPException(status_code=404, detail="Perspective owner not found in league")

    # --- Build simulation DataFrames from DB (no CSV files) ---

    # 1. Active players
    active_pid_subq = (
        db.query(distinct(models.PlayerSeason.player_id))
        .filter(models.PlayerSeason.is_active == True)
        .subquery()
    )
    player_rows = (
        db.query(models.Player)
        .filter(
            models.Player.id.in_(active_pid_subq),
            models.Player.position.in_({"QB", "RB", "WR", "TE", "K", "DEF"}),
        )
        .all()
    )
    players_df = pd.DataFrame(
        [{"Player_ID": p.id, "PlayerName": p.name, "PositionID": p.position or ""} for p in player_rows]
    )

    # 2. Bid statistics aggregated from draft_picks (all-time, league-scoped)
    bid_agg = (
        db.query(
            models.DraftPick.player_id,
            func.count(models.DraftPick.id).label("appearances"),
            func.avg(models.DraftPick.amount).label("avg_bid"),
        )
        .filter(models.DraftPick.league_id == current_user.league_id)
        .group_by(models.DraftPick.player_id)
        .all()
    )
    bid_stats_map: dict[int, dict] = {
        row.player_id: {
            "appearances": int(row.appearances or 0),
            "avg_bid": float(row.avg_bid or 0.0),
        }
        for row in bid_agg
    }

    # 3. Historical rankings from draft_values joined to players
    draft_year = datetime.now().year
    dv_rows = (
        db.query(models_draft_value.DraftValue, models.Player)
        .join(models.Player, models.Player.id == models_draft_value.DraftValue.player_id)
        .filter(models_draft_value.DraftValue.season == draft_year)
        .all()
    )
    historical_rankings_rows = []
    for dv, player in dv_rows:
        bs = bid_stats_map.get(dv.player_id, {})
        historical_rankings_rows.append({
            "player_id": dv.player_id,
            "player_name": player.name,
            "position": player.position or "",
            "predicted_auction_value": float(dv.avg_auction_value or 1.0),
            "model_score": float(dv.model_score or 0.0),
            "appearances": bs.get("appearances", 0),
            "avg_bid": bs.get("avg_bid", 0.0),
        })
    # Include any players with bid history but no draft_values row this season
    for player_id, bs in bid_stats_map.items():
        if not any(r["player_id"] == player_id for r in historical_rankings_rows):
            player = db.query(models.Player).filter(models.Player.id == player_id).first()
            if player:
                historical_rankings_rows.append({
                    "player_id": player_id,
                    "player_name": player.name,
                    "position": player.position or "",
                    "predicted_auction_value": bs["avg_bid"] or 1.0,
                    "model_score": 0.0,
                    "appearances": bs["appearances"],
                    "avg_bid": bs["avg_bid"],
                })
    historical_rankings_df = pd.DataFrame(
        historical_rankings_rows
        if historical_rankings_rows
        else [{"player_id": 0, "predicted_auction_value": 1.0, "model_score": 0.0}]
    )

    # 4. Draft results from draft_picks (league-scoped), joined to player for PositionID
    draft_picks_db = (
        db.query(models.DraftPick, models.Player)
        .join(models.Player, models.Player.id == models.DraftPick.player_id, isouter=True)
        .filter(models.DraftPick.league_id == current_user.league_id)
        .all()
    )
    draft_results_df = pd.DataFrame(
        [
            {
                "OwnerID": pick.owner_id,
                "PlayerID": pick.player_id,
                "PositionID": (player.position if player else "") or "",
                "WinningBid": float(pick.amount or 0),
                "Year": int(pick.year or draft_year),
            }
            for pick, player in draft_picks_db
        ]
    )
    if draft_results_df.empty:
        raise HTTPException(
            status_code=400,
            detail="No draft history found for this league. Complete at least one draft before running a simulation.",
        )

    # 5. Draft budgets (league-scoped)
    budget_rows = (
        db.query(models.DraftBudget)
        .filter(models.DraftBudget.league_id == current_user.league_id)
        .all()
    )
    budget_df = pd.DataFrame(
        [{"OwnerID": b.owner_id, "DraftBudget": float(b.total_budget or 200)} for b in budget_rows]
    )

    safe_iterations = max(50, min(int(payload.iterations), 10000))
    safe_teams_count = max(2, min(int(payload.teams_count), 20))
    safe_roster_size = max(4, min(int(payload.roster_size), 30))
    safe_target_key_players = max(5, min(int(payload.target_key_players), 50))

    strategy = payload.strategy
    simulation_config = SimulationConfig(
        iterations=safe_iterations,
        seed=int(payload.seed),
        target_owner_id=perspective_owner_id,
        teams_count=safe_teams_count,
        roster_size=safe_roster_size,
        target_key_players=safe_target_key_players,
        focal_owner_id=perspective_owner_id,
        focal_aggressiveness_multiplier=float(strategy.aggressiveness_multiplier),
        focal_position_weights=strategy.position_weights,
        focal_risk_tolerance=float(strategy.risk_tolerance),
        focal_player_reliability_weight=float(strategy.player_reliability_weight),
    )

    try:
        result = run_monte_carlo_draft_simulation(
            draft_results_df=draft_results_df,
            players_df=players_df,
            historical_rankings_df=historical_rankings_df,
            budget_df=budget_df,
            config=simulation_config,
        )
    except Exception as exc:
        logger.exception(
            "draft_simulation.failed user_id=%s perspective_owner_id=%s",
            current_user.id,
            perspective_owner_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Simulation failed. {str(exc) or 'Please try again.'}",
        )

    focal_summary: dict[str, Any] = {}
    if not result.owner_summary.empty:
        focal_summary = result.owner_summary.iloc[0].to_dict()

    focal_distribution = summarize_team_distribution(result.team_metrics, owner_id=perspective_owner_id)

    key_target_rows: list[dict[str, Any]] = []
    if not result.draft_picks.empty:
        pos_col = "position" if "position" in result.draft_picks.columns else None
        top_targets = (
            result.draft_picks[
                ["player_id", "player_name", "predicted_auction_value"]
                + ([pos_col] if pos_col else [])
            ]
            .drop_duplicates(subset=["player_id"])
            .sort_values("predicted_auction_value", ascending=False)
            .head(safe_target_key_players)
        )
        probability_df = key_target_probabilities(
            result.draft_picks,
            owner_id=perspective_owner_id,
            target_player_ids=top_targets["player_id"].tolist(),
            iterations=safe_iterations,
        )
        merge_cols = ["player_id", "player_name", "predicted_auction_value"]
        if pos_col:
            merge_cols.append(pos_col)
        probability_df = probability_df.merge(
            top_targets[merge_cols],
            on="player_id",
            how="left",
        ).sort_values("probability", ascending=False)

        # avg_bid sourced from live draft_picks aggregates (already computed above)
        avg_bid_lookup: dict[int, float] = {
            pid: bs["avg_bid"] for pid, bs in bid_stats_map.items()
        }

        # Derive rival bidders per target player across simulation iterations
        # A rival is any non-focal owner who won the player in at least one iteration
        rival_lookup: dict[int, list[dict[str, Any]]] = {}
        try:
            picks_df = result.draft_picks.copy()
            target_ids = set(top_targets["player_id"].tolist())
            target_picks = picks_df[
                (picks_df["player_id"].isin(target_ids)) &
                (picks_df["owner_id"] != perspective_owner_id)
            ]
            if not target_picks.empty:
                rival_counts = (
                    target_picks.groupby(["player_id", "owner_id"])
                    .size()
                    .reset_index(name="win_count")
                    .sort_values(["player_id", "win_count"], ascending=[True, False])
                )
                # Map owner_id -> name from league users
                owner_name_map = {
                    u.id: (u.team_name or u.username or f"Owner {u.id}")
                    for u in db.query(models.User).filter(
                        models.User.league_id == current_user.league_id,
                        models.User.is_superuser == False,
                    ).all()
                }
                for pid, group in rival_counts.groupby("player_id"):
                    rival_lookup[int(pid)] = [
                        {
                            "owner_id": int(row.owner_id),
                            "owner_name": owner_name_map.get(int(row.owner_id), f"Owner {int(row.owner_id)}"),
                            "win_count": int(row.win_count),
                        }
                        for row in group.head(3).itertuples(index=False)
                    ]
        except Exception:
            pass

        key_target_rows = [
            {
                "player_id": int(row.player_id),
                "player_name": row.player_name,
                "position": str(getattr(row, pos_col, "") or "") if pos_col else "",
                "probability": float(row.probability),
                "hit_count": int(row.hit_count),
                "avg_bid": avg_bid_lookup.get(int(row.player_id), 0.0),
                "predicted_auction_value": float(getattr(row, "predicted_auction_value", 0) or 0),
                "rival_bidders": rival_lookup.get(int(row.player_id), []),
            }
            for row in probability_df.itertuples(index=False)
        ]

    league_owner_means = (
        result.team_metrics.groupby("owner_id", as_index=False)
        .agg(
            avg_projected_points=("projected_points", "mean"),
            avg_total_spend=("total_spend", "mean"),
        )
    )
    focal_context_row = league_owner_means[league_owner_means["owner_id"] == perspective_owner_id]

    focal_avg_points = (
        float(focal_context_row.iloc[0]["avg_projected_points"]) if not focal_context_row.empty else 0.0
    )
    league_avg_points = (
        float(league_owner_means["avg_projected_points"].mean()) if not league_owner_means.empty else 0.0
    )

    logger.info(
        "draft_simulation.success user_id=%s perspective_owner_id=%s simulation_runs=%s",
        current_user.id,
        perspective_owner_id,
        safe_iterations,
    )

    return {
        "perspective_owner_id": perspective_owner_id,
        "league_id": current_user.league_id,
        "iterations": safe_iterations,
        "focal_owner_summary": focal_summary,
        "focal_points_distribution": focal_distribution,
        "key_target_probabilities": key_target_rows,
        "league_context": {
            "focal_avg_projected_points": focal_avg_points,
            "league_avg_projected_points": league_avg_points,
            "delta_vs_league_avg": float(focal_avg_points - league_avg_points),
        },
        "used_strategy": {
            "aggressiveness_multiplier": simulation_config.focal_aggressiveness_multiplier,
            "position_weights": simulation_config.resolved_focal_position_weights(),
            "risk_tolerance": simulation_config.focal_risk_tolerance,
            "player_reliability_weight": simulation_config.focal_player_reliability_weight,
        },
    }

@router.post("/draft-pick")
async def draft_player(pick: DraftPickCreate, db: Session = Depends(get_db)):
    boundary_report = validate_draft_pick_boundary(
        {
            "owner_id": pick.owner_id,
            "player_id": pick.player_id,
            "amount": pick.amount,
            "session_id": pick.session_id,
            "year": pick.year,
        }
    )
    if not boundary_report.valid:
        raise HTTPException(status_code=400, detail=boundary_report.errors)

    dynamic_report = validate_draft_pick_dynamic_rules(
        {
            "owner_id": pick.owner_id,
            "player_id": pick.player_id,
            "amount": pick.amount,
            "session_id": pick.session_id,
            "year": pick.year,
        }
    )
    if not dynamic_report.valid:
        raise HTTPException(status_code=400, detail=dynamic_report.errors)

    # 1. Validation Logic
    player = db.query(models.Player).filter(models.Player.id == pick.player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    existing_pick = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == pick.player_id,
        models.DraftPick.session_id == pick.session_id
    ).first()
    
    if existing_pick:
        raise HTTPException(status_code=400, detail="Player already drafted!")

    owner = db.query(models.User).filter(models.User.id == pick.owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    if pick.amount < 1:
        raise HTTPException(status_code=400, detail="Bid amount must be at least $1")

    league = None
    if owner.league_id:
        league = db.query(models.League).filter(models.League.id == owner.league_id).first()
        if league and (league.draft_status or "PRE_DRAFT") != "COMPLETED":
            league.draft_status = "ACTIVE"

    # 2. Save to Database
    year_value = pick.year
    if year_value is None:
        settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == owner.league_id).first()
        year_value = settings.draft_year if settings and settings.draft_year else datetime.utcnow().year

    settings = _get_league_settings(db, owner.league_id)
    roster_size = int(settings.roster_size) if settings and settings.roster_size else 14

    owner_picks = (
        db.query(models.DraftPick)
        .filter(
            models.DraftPick.session_id == pick.session_id,
            models.DraftPick.owner_id == owner.id,
        )
        .all()
    )
    picks_spend = sum(int(row.amount or 0) for row in owner_picks)

    league_keepers = _get_keeper_carryover_rows(
        db,
        league_id=owner.league_id,
        draft_year=year_value,
    )
    keeper_player_ids = {entry.player_id for entry in league_keepers}
    if pick.player_id in keeper_player_ids:
        raise HTTPException(
            status_code=400,
            detail="Player is already locked as a prior-season keeper",
        )

    owner_keeper_rows = [entry for entry in league_keepers if entry.owner_id == owner.id]
    keeper_spend = sum(int(entry.keep_cost or 0) for entry in owner_keeper_rows)

    owner_total_budget = _get_owner_total_budget(
        db,
        league_id=owner.league_id,
        owner_id=owner.id,
        draft_year=year_value,
    )

    total_filled_slots = len(owner_picks) + len(owner_keeper_rows)
    if total_filled_slots >= roster_size:
        raise HTTPException(status_code=400, detail="Owner roster is full")

    remaining_budget = owner_total_budget - picks_spend - keeper_spend
    empty_spots = roster_size - total_filled_slots
    max_bid = remaining_budget - (empty_spots - 1) if empty_spots > 0 else 0

    if pick.amount > max_bid:
        raise HTTPException(
            status_code=400,
            detail=f"Bid exceeds max allowed (${max(0, max_bid)})",
        )

    new_pick = models.DraftPick(
        player_id=pick.player_id,
        owner_id=pick.owner_id,
        year=year_value,
        amount=pick.amount,
        session_id=pick.session_id,
        league_id=owner.league_id,
        timestamp=datetime.utcnow().isoformat()
    )
    db.add(new_pick)
    db.commit()
    db.refresh(new_pick)

    # 3. REAL-TIME MAGIC (The new addition!)
    # Notify all connected users that a pick was made!
    await manager.broadcast({
        "event": "PICK_MADE",
        "player_id": pick.player_id,
        "owner_id": pick.owner_id,
        "amount": pick.amount,
        "player_name": _normalize_player_name(player.name) # useful for the ticker
    })

    return new_pick

# --- NEW: POST /draft/pick (alias for /draft-pick) ---
@router.post("/draft/pick")
async def draft_player_alias(pick: DraftPickCreate, db: Session = Depends(get_db)):
    return await draft_player(pick, db)

# --- 4. FUTURE ENDPOINTS (Auction / State) ---

@router.get("/draft/state/{league_id}")
def get_draft_state(league_id: int, db: Session = Depends(get_db)):
    return {"status": "active", "league_id": league_id}

# --- 5. THE WEBSOCKET ENDPOINT ---
@router.websocket("/ws/{league_id}")
async def websocket_endpoint(websocket: WebSocket, league_id: int):
    await manager.connect(websocket)
    try:
        while True:
            # tailored to wait for messages if you add chat later
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
