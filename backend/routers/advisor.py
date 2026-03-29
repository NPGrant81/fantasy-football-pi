import os
import time
import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from .league import _answer_history_question
from ..services.draft_rankings_service import get_historical_rankings

# Optional import for testing environments
# the `google-genai` SDK (>=1.64.0) provides the `genai` namespace
# older packages such as google-generativeai or google-ai-generativelanguage
# have been removed from requirements.
try:
    from google import genai
except ImportError:
    genai = None 

router = APIRouter(prefix="/advisor", tags=["AI"])
_RANKING_CACHE: dict[tuple[int, int, int], tuple[float, list[dict]]] = {}
_RANKING_CACHE_TTL_SECONDS = 15.0
logger = logging.getLogger(__name__)


def _looks_like_history_query(question: str) -> bool:
    normalized = str(question or "").lower()
    return any(
        phrase in normalized
        for phrase in (
            "most points",
            "most wins",
            "highest scoring",
            "highest-scoring",
            "champion",
            "who won",
            "all-time",
            "history",
        )
    )


@router.get("/status")
def get_advisor_status():
    api_key = os.environ.get("GEMINI_API_KEY")
    has_genai_sdk = bool(genai)
    enabled = bool(api_key) and has_genai_sdk
    return {"enabled": enabled}


class AdvisorRequest(BaseModel):
    user_query: str
    username: Optional[str] = None
    league_id: Optional[int] = None


class DraftDayState(BaseModel):
    drafted_player_ids: list[int] = Field(default_factory=list)
    remaining_budget_by_owner: dict[int, float] = Field(default_factory=dict)
    remaining_slots_by_owner: dict[int, int] = Field(default_factory=dict)
    position_counts_by_owner: dict[int, dict[str, int]] = Field(default_factory=dict)
    recent_nominations: list[str] = Field(default_factory=list)


class DraftDayEventRequest(BaseModel):
    owner_id: int
    season: int
    league_id: int
    event_type: Literal["nomination", "bid_update", "roster_update", "user_query"]
    player_id: Optional[int] = None
    current_bid: Optional[float] = None
    compared_player_id: Optional[int] = None
    question: Optional[str] = None
    draft_state: DraftDayState = DraftDayState()


class DraftDayMessageResponse(BaseModel):
    event_type: str
    message_type: Literal["recommendation", "alert", "explanation", "comparison", "strategy_summary"]
    headline: str
    body: str
    recommended_bid: Optional[float] = None
    value_tier: Optional[str] = None
    risk_score: Optional[float] = None
    bidding_war_likelihood: Optional[float] = None
    suggested_alternatives: list[dict[str, object]] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    quick_actions: list[str] = Field(default_factory=lambda: ["Compare", "Simulate", "Explain"])


class DraftDayQueryRequest(BaseModel):
    owner_id: int
    season: int
    league_id: int
    player_id: Optional[int] = None
    current_bid: Optional[float] = None
    compared_player_id: Optional[int] = None
    question: Optional[str] = None
    draft_state: DraftDayState = Field(default_factory=DraftDayState)


def _load_rankings_cached(
    db: Session,
    *,
    season: int,
    league_id: int,
    owner_id: int,
    limit: int = 120,
) -> list[dict]:
    cache_key = (int(season), int(league_id), int(owner_id))
    now = time.time()
    cached = _RANKING_CACHE.get(cache_key)
    if cached and (now - cached[0]) <= _RANKING_CACHE_TTL_SECONDS:
        return cached[1]

    rows = get_historical_rankings(
        db,
        season=int(season),
        limit=max(40, min(int(limit), 200)),
        league_id=int(league_id),
        owner_id=int(owner_id),
        position=None,
    )
    _RANKING_CACHE[cache_key] = (now, rows)
    return rows


def _player_lookup(db: Session, player_id: int | None):
    if not player_id:
        return None
    return db.query(models.Player).filter(models.Player.id == int(player_id)).first()


def _position_imbalance_alert(
    *,
    owner_id: int,
    position_counts_by_owner: dict[int, dict[str, int]],
) -> str | None:
    owner_counts = position_counts_by_owner.get(owner_id) or {}
    if not owner_counts:
        return None

    rb_count = int(owner_counts.get("RB", 0))
    wr_count = int(owner_counts.get("WR", 0))
    if rb_count >= wr_count + 2:
        return "You are becoming WR-light relative to RB depth."
    if wr_count >= rb_count + 2:
        return "You are becoming RB-light relative to WR depth."
    return None


def _overspending_alert(
    *,
    owner_id: int,
    remaining_budget_by_owner: dict[int, float],
    remaining_slots_by_owner: dict[int, int],
) -> str | None:
    budget = remaining_budget_by_owner.get(owner_id)
    slots = remaining_slots_by_owner.get(owner_id)
    if budget is None or slots is None or int(slots) <= 0:
        return None
    avg_dollars_per_slot = float(budget) / float(max(int(slots), 1))
    if avg_dollars_per_slot < 4:
        return "Overspending risk: your average dollars-per-slot is dropping into low flexibility range."
    return None


def _run_starting_alert(recent_nominations: list[str]) -> str | None:
    normalized = [str(position or "").upper() for position in recent_nominations if position]
    if len(normalized) < 4:
        return None
    tail = normalized[-4:]
    if len(set(tail)) == 1:
        return f"League dynamic shift: {tail[0]} run appears to be starting."
    return None


def _build_alternatives(
    rankings: list[dict],
    *,
    position: str | None,
    excluded_ids: set[int],
    top_n: int = 3,
) -> list[dict[str, object]]:
    candidates = []
    for row in rankings:
        player_id = int(row.get("player_id") or 0)
        if player_id in excluded_ids:
            continue
        if position and str(row.get("position") or "").upper() != str(position).upper():
            continue
        candidates.append(
            {
                "player_id": player_id,
                "player_name": row.get("player_name"),
                "position": row.get("position"),
                "predicted_value": float(row.get("predicted_auction_value") or 0),
                "tier": row.get("consensus_tier"),
            }
        )
        if len(candidates) >= top_n:
            break
    return candidates


def _find_ranking_row(rankings: list[dict], player_id: int | None):
    if not player_id:
        return None
    for row in rankings:
        if int(row.get("player_id") or 0) == int(player_id):
            return row
    return None


def _safe_risk_score(row: dict | None) -> float:
    if not row:
        return 50.0
    consistency = float(row.get("scoring_consistency_factor") or 1.0)
    late_start = float(row.get("late_start_consistency_factor") or 1.0)
    injury_split = float(row.get("injury_split_factor") or 1.0)
    team_change = float(row.get("team_change_factor") or 1.0)
    reliability = consistency * late_start * injury_split * team_change
    return float(round(max(0.0, min(100.0, (1.0 - min(max(reliability, 0.0), 1.5) / 1.5) * 100.0)), 2))


def _safe_recommended_bid(
    *,
    row: dict | None,
    owner_id: int,
    current_bid: float | None,
    draft_state: DraftDayState,
) -> float:
    predicted_value = float((row or {}).get("predicted_auction_value") or 1.0)
    baseline_bid = max(float(current_bid or 1.0), predicted_value * 0.92)
    budget = draft_state.remaining_budget_by_owner.get(owner_id)
    slots = draft_state.remaining_slots_by_owner.get(owner_id)
    if budget is None or slots is None:
        return float(round(baseline_bid, 2))
    max_bid = max(float(budget) - float(max(int(slots), 1) - 1), 1.0)
    return float(round(min(baseline_bid, max_bid), 2))


def _bidding_war_likelihood(row: dict | None, current_bid: float | None) -> float:
    if not row:
        return 40.0
    predicted_value = float(row.get("predicted_auction_value") or 1.0)
    bid = float(current_bid or 0)
    pressure = bid / max(predicted_value, 1.0)
    tier = str(row.get("consensus_tier") or "C").upper()
    tier_bonus = {"S": 20, "A": 12, "B": 7, "C": 3, "D": 0}.get(tier, 0)
    likelihood = min(95.0, max(10.0, 30.0 + pressure * 35.0 + tier_bonus))
    return float(round(likelihood, 2))


@router.post("/draft-day/event", response_model=DraftDayMessageResponse)
def draft_day_event(request: DraftDayEventRequest, db: Session = Depends(get_db)):
    rankings = _load_rankings_cached(
        db,
        season=request.season,
        league_id=request.league_id,
        owner_id=request.owner_id,
        limit=150,
    )
    ranking_row = _find_ranking_row(rankings, request.player_id)
    player = _player_lookup(db, request.player_id)
    position = (ranking_row or {}).get("position") or (player.position if player else None)
    player_name = (ranking_row or {}).get("player_name") or (player.name if player else "the nominated player")

    recommended_bid = _safe_recommended_bid(
        row=ranking_row,
        owner_id=request.owner_id,
        current_bid=request.current_bid,
        draft_state=request.draft_state,
    )
    risk_score = _safe_risk_score(ranking_row)
    war_likelihood = _bidding_war_likelihood(ranking_row, request.current_bid)

    excluded_ids = set(int(pid) for pid in request.draft_state.drafted_player_ids)
    if request.player_id:
        excluded_ids.add(int(request.player_id))

    alternatives = _build_alternatives(
        rankings,
        position=position,
        excluded_ids=excluded_ids,
        top_n=3,
    )

    alerts: list[str] = []
    imbalance = _position_imbalance_alert(
        owner_id=request.owner_id,
        position_counts_by_owner=request.draft_state.position_counts_by_owner,
    )
    if imbalance:
        alerts.append(imbalance)
    overspending = _overspending_alert(
        owner_id=request.owner_id,
        remaining_budget_by_owner=request.draft_state.remaining_budget_by_owner,
        remaining_slots_by_owner=request.draft_state.remaining_slots_by_owner,
    )
    if overspending:
        alerts.append(overspending)
    run_shift = _run_starting_alert(request.draft_state.recent_nominations)
    if run_shift:
        alerts.append(run_shift)

    if request.event_type == "nomination":
        body = (
            f"{player_name} projects as tier {(ranking_row or {}).get('consensus_tier', 'C')} with risk {risk_score:.1f}. "
            f"Recommended bid cap is ${recommended_bid:.2f}."
        )
        if alternatives:
            body += f" If this escalates, pivot options include {', '.join(str(item['player_name']) for item in alternatives[:2])}."
        return DraftDayMessageResponse(
            event_type=request.event_type,
            message_type="recommendation",
            headline=f"Nomination guidance: {player_name}",
            body=body,
            recommended_bid=recommended_bid,
            value_tier=(ranking_row or {}).get("consensus_tier"),
            risk_score=risk_score,
            bidding_war_likelihood=war_likelihood,
            suggested_alternatives=alternatives,
            alerts=alerts,
        )

    if request.event_type == "bid_update":
        current_bid = float(request.current_bid or 0)
        exceeds_plan = current_bid > recommended_bid
        body = (
            f"Current bid is ${current_bid:.2f}."
            f" Suggested cap is ${recommended_bid:.2f}."
            f" Bidding-war likelihood is {war_likelihood:.1f}%."
        )
        if exceeds_plan:
            body += " This price is above your plan; consider passing and pivoting."
        return DraftDayMessageResponse(
            event_type=request.event_type,
            message_type="alert" if exceeds_plan else "recommendation",
            headline=f"Bid update: {player_name}",
            body=body,
            recommended_bid=recommended_bid,
            value_tier=(ranking_row or {}).get("consensus_tier"),
            risk_score=risk_score,
            bidding_war_likelihood=war_likelihood,
            suggested_alternatives=alternatives,
            alerts=alerts,
        )

    if request.event_type == "roster_update":
        summary = alerts or ["Roster remains aligned with current draft plan."]
        return DraftDayMessageResponse(
            event_type=request.event_type,
            message_type="strategy_summary",
            headline="Strategy monitor update",
            body=" ".join(summary),
            suggested_alternatives=alternatives,
            alerts=alerts,
        )

    question_text = (request.question or "").lower()
    if "compare" in question_text and request.player_id and request.compared_player_id:
        left = _find_ranking_row(rankings, request.player_id)
        right = _find_ranking_row(rankings, request.compared_player_id)
        if not left or not right:
            raise HTTPException(status_code=404, detail="Unable to compare requested players")
        left_name = str(left.get("player_name"))
        right_name = str(right.get("player_name"))
        left_score = float(left.get("final_score") or 0)
        right_score = float(right.get("final_score") or 0)
        winner_name = left_name if left_score >= right_score else right_name
        body = (
            f"{left_name} score {left_score:.2f} vs {right_name} score {right_score:.2f}. "
            f"Preferred target right now is {winner_name}."
        )
        return DraftDayMessageResponse(
            event_type=request.event_type,
            message_type="comparison",
            headline=f"Comparison: {left_name} vs {right_name}",
            body=body,
            alerts=alerts,
        )

    body = (
        f"For {player_name}, recommended bid cap is ${recommended_bid:.2f}, tier {(ranking_row or {}).get('consensus_tier', 'C')}, "
        f"risk {risk_score:.1f}."
    )
    return DraftDayMessageResponse(
        event_type=request.event_type,
        message_type="explanation",
        headline="Draft Day answer",
        body=body,
        recommended_bid=recommended_bid,
        value_tier=(ranking_row or {}).get("consensus_tier"),
        risk_score=risk_score,
        bidding_war_likelihood=war_likelihood,
        suggested_alternatives=alternatives,
        alerts=alerts,
    )


@router.post("/draft-day/query", response_model=DraftDayMessageResponse)
def draft_day_query(request: DraftDayQueryRequest, db: Session = Depends(get_db)):
    event_request = DraftDayEventRequest(
        owner_id=request.owner_id,
        season=request.season,
        league_id=request.league_id,
        event_type="user_query",
        player_id=request.player_id,
        current_bid=request.current_bid,
        compared_player_id=request.compared_player_id,
        question=request.question,
        draft_state=request.draft_state,
    )
    return draft_day_event(event_request, db)


@router.post("/ask")
def ask_gemini(request: AdvisorRequest, db: Session = Depends(get_db)):
    if request.league_id and _looks_like_history_query(request.user_query):
        history_result = _answer_history_question(
            db=db,
            league_id=int(request.league_id),
            question=request.user_query,
        )
        if history_result.get("intent") != "unsupported":
            return {"response": str(history_result.get("answer") or "No answer available.")}

    # 1. Check for API Key and genai availability (Lazy Load)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not genai:
        logger.warning(
            "Advisor unavailable: missing Gemini configuration (has_api_key=%s, has_genai_sdk=%s)",
            bool(api_key),
            bool(genai),
        )
        return {"response": "⚠️ The Commissioner is offline. (Missing GEMINI_API_KEY or genai package)"}

    # 2. FETCH CONTEXT (League-specific rules)
    rules = []
    league_name = "your league"
    if request.league_id:
        rules = db.query(models.ScoringRule).filter(models.ScoringRule.league_id == request.league_id).all()
        league = db.query(models.League).filter(models.League.id == request.league_id).first()
        if league:
            league_name = league.name
    else:
        rules = db.query(models.ScoringRule).all()

    if not rules:
        rules_text = "Standard PPR Scoring"
    else:
        # use point_value since the model field is named that (previously caused a 500 error)
        rules_text = "\n".join([f"- {r.category}: {r.point_value} pts" for r in rules])

    # optional: include information about the requesting user's team if available
    roster_line = ""
    if request.username and request.league_id:
        user = (
            db.query(models.User)
            .filter(
                models.User.username == request.username,
                models.User.league_id == request.league_id,
            )
            .first()
        )
        if user:
            roster_line = f"USER TEAM: {user.team_name or 'N/A'} ({user.username})\n"

    # 3. CONSTRUCT PROMPT
    prompt = f"""
    You are a Fantasy Football Assistant for the '{league_name}'.
    
    LEAGUE SCORING RULES:
    {rules_text}
    
    {roster_line}
    USER: {request.username or 'A user'}
    QUESTION:
    {request.user_query}
    
    Answer briefly and specifically based on the scoring rules above.
    """

    # 4. CALL GEMINI
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt
        )
        return {"response": response.text}
    except Exception as e:
        print(f"Gemini Error: {e}")
        return {"response": "I'm having trouble connecting to the league office. Try again later."}