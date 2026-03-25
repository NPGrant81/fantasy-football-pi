from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import desc, or_, func, case
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from ..database import get_db
from .. import models
from ..core.security import get_current_user, check_is_commissioner # Use our new auth system
from ..services.ledger_service import owner_balance, owner_draft_budget_total, owner_has_incoming_credits, record_ledger_entry
from ..services.standings_service import owner_standings_sort_key
from ..services.player_service import normalize_display_name as _normalize_player_name
from ..services.validation_service import (
    validate_league_settings_boundary,
    validate_league_settings_dynamic_rules,
)
import secrets
import string
import logging
from utils.email_sender import send_invite_email

logger = logging.getLogger(__name__)

# FIX 1: Changed prefix to "/leagues" (Plural) to match Frontend
router = APIRouter(
    prefix="/leagues",
    tags=["League"]
)

# --- Schemas ---
class LeagueCreate(BaseModel):
    name: str

class LeagueSummary(BaseModel):
    id: int
    name: str
    draft_status: str
    divisions_enabled: Optional[bool] = None
    division_count: Optional[int] = None
    division_config_status: Optional[str] = None
    requires_reseed_review: Optional[bool] = None

class LeagueNewsItem(BaseModel):
    type: str
    title: str
    timestamp: str

# --- Update the Request Schema ---
class AddMemberRequest(BaseModel):
    username: str
    email: Optional[str] = None # Now accepts email
    league_id: Optional[int] = None

# NEW: Schema for updating settings
class SettingsUpdate(BaseModel):
    roster_size: int
    salary_cap: int
    starting_slots: Dict[str, int] # e.g. {"QB": 1, "WR": 3}

# --- UPDATED SCHEMA (Supports Rules + Settings) ---
class ScoringRuleSchema(BaseModel):
    category: str
    event_name: str
    description: Optional[str] = None
    range_min: float = 0
    range_max: float = 9999.99
    point_value: float
    calculation_type: str = "flat_bonus"  # per_unit|flat_bonus
    applicable_positions: List[str] = []

class LeagueConfigFull(BaseModel):
    roster_size: int
    salary_cap: int
    starting_slots: Dict[str, int]
    waiver_deadline: Optional[str] = None
    starting_waiver_budget: Optional[int] = None
    waiver_system: Optional[str] = None
    waiver_tiebreaker: Optional[str] = None
    trade_deadline: Optional[str] = None  # new field
    draft_year: Optional[int] = None
    scoring_rules: List[ScoringRuleSchema]

class BudgetEntry(BaseModel):
    owner_id: int
    total_budget: int

class BudgetUpdateRequest(BaseModel):
    year: int
    budgets: List[BudgetEntry]

# --- Waiver-specific schemas ---
class WaiverBudgetSchema(BaseModel):
    owner_id: int
    starting_budget: int
    remaining_budget: int
    spent_budget: int


class LedgerEntrySchema(BaseModel):
    id: int
    created_at: Optional[str] = None
    season_year: Optional[int] = None
    currency_type: str
    transaction_type: str
    amount: int
    from_owner_id: Optional[int] = None
    to_owner_id: Optional[int] = None
    direction: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    notes: Optional[str] = None


class LedgerStatementSchema(BaseModel):
    league_id: int
    owner_id: int
    currency_type: Optional[str] = None
    season_year: Optional[int] = None
    balance: int
    entry_count: int
    entries: List[LedgerEntrySchema]


def canonicalize_lineup_slots(slots: Dict[str, int] | None) -> Dict[str, int]:
    raw_slots = dict(slots or {})

    def parse_int(key: str, default: int = 0) -> int:
        value = raw_slots.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    active_roster_size = max(5, min(12, parse_int("ACTIVE_ROSTER_SIZE", 9)))
    max_limits = {
        "QB": max(1, min(3, parse_int("MAX_QB", parse_int("QB", 1)))),
        "RB": max(1, min(5, parse_int("MAX_RB", parse_int("RB", 3)))),
        "WR": max(1, min(5, parse_int("MAX_WR", parse_int("WR", 3)))),
        "TE": max(1, min(3, parse_int("MAX_TE", parse_int("TE", 2)))),
        "K": max(0, min(1, parse_int("MAX_K", parse_int("K", 1)))),
        "DEF": 1,
        "FLEX": max(0, min(1, parse_int("MAX_FLEX", parse_int("FLEX", 1)))),
    }

    mins = {
        "QB": 1 if max_limits["QB"] > 0 else 0,
        "RB": min(2, max_limits["RB"]) if max_limits["RB"] > 0 else 0,
        "WR": min(2, max_limits["WR"]) if max_limits["WR"] > 0 else 0,
        "TE": 1 if max_limits["TE"] > 0 else 0,
        "K": 1 if max_limits["K"] > 0 else 0,
        "DEF": 1 if max_limits["DEF"] > 0 else 0,
        "FLEX": 1 if max_limits["FLEX"] > 0 else 0,
    }

    total_mins = sum(mins.values())
    if total_mins > active_roster_size:
        for position in ("FLEX", "K", "TE", "WR", "RB", "QB", "DEF"):
            while mins[position] > 0 and total_mins > active_roster_size:
                mins[position] -= 1
                total_mins -= 1
            if total_mins <= active_roster_size:
                break

    return {
        **raw_slots,
        "QB": mins["QB"],
        "RB": mins["RB"],
        "WR": mins["WR"],
        "TE": mins["TE"],
        "K": mins["K"],
        "DEF": mins["DEF"],
        "FLEX": mins["FLEX"],
        "ACTIVE_ROSTER_SIZE": active_roster_size,
        "MAX_QB": max_limits["QB"],
        "MAX_RB": max_limits["RB"],
        "MAX_WR": max_limits["WR"],
        "MAX_TE": max_limits["TE"],
        "MAX_K": max_limits["K"],
        "MAX_DEF": max_limits["DEF"],
        "MAX_FLEX": max_limits["FLEX"],
        "ALLOW_PARTIAL_LINEUP": 1 if parse_int("ALLOW_PARTIAL_LINEUP", 0) == 1 else 0,
        "REQUIRE_WEEKLY_SUBMIT": 1 if parse_int("REQUIRE_WEEKLY_SUBMIT", 1) == 1 else 0,
    }


# --- Helper function to format validation errors as readable string ---
def format_validation_errors(errors: Dict[str, Any]) -> str:
    """
    Convert validation error dict to a readable error message.
    Handles both pydantic format and manual validation format.
    """
    messages = []
    
    # Handle pydantic validation errors (detail: list of error dicts)
    if "detail" in errors and isinstance(errors["detail"], list):
        for err in errors["detail"]:
            if isinstance(err, dict):
                field = err.get("loc", ["unknown"])[-1]
                msg = err.get("msg", "Invalid value")
                messages.append(f"{field}: {msg}")
    # Handle manual validation errors (dict with lists of error strings)
    else:
        for field, field_errors in errors.items():
            if isinstance(field_errors, list):
                # Join multiple errors for same field with "; "
                error_text = "; ".join(field_errors)
                messages.append(f"{field}: {error_text}")
            else:
                messages.append(f"{field}: {field_errors}")
    
    # Return joined message or generic fallback
    return " | ".join(messages) if messages else "Validation failed"


def validate_lineup_rules(config: LeagueConfigFull) -> None:
    slots = config.starting_slots or {}

    def parse_int(key: str, default: int = 0) -> int:
        value = slots.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be an integer.",
            )

    active_roster_size = parse_int("ACTIVE_ROSTER_SIZE", 9)
    if active_roster_size < 5 or active_roster_size > 12:
        raise HTTPException(
            status_code=400,
            detail="ACTIVE_ROSTER_SIZE must be between 5 and 12.",
        )

    qb = parse_int("MAX_QB", 3)
    rb = parse_int("MAX_RB", 5)
    wr = parse_int("MAX_WR", 5)
    te = parse_int("MAX_TE", 3)
    k = parse_int("MAX_K", 1)
    defense = parse_int("MAX_DEF", 1)
    flex = parse_int("MAX_FLEX", 1)

    rules = {
        "QB": (qb, 1, 3),
        "RB": (rb, 1, 5),
        "WR": (wr, 1, 5),
        "TE": (te, 1, 3),
    }
    for pos, (actual, minimum, maximum) in rules.items():
        if actual < minimum or actual > maximum:
            raise HTTPException(
                status_code=400,
                detail=f"MAX_{pos} must be between {minimum} and {maximum}.",
            )

    if k < 0 or k > 1:
        raise HTTPException(status_code=400, detail="MAX_K must be 0 or 1.")

    if defense != 1:
        raise HTTPException(status_code=400, detail="MAX_DEF must be exactly 1.")

    if flex < 0 or flex > 1:
        raise HTTPException(status_code=400, detail="MAX_FLEX must be 0 or 1.")

    starter_counts = {
        "QB": parse_int("QB", 0),
        "RB": parse_int("RB", 0),
        "WR": parse_int("WR", 0),
        "TE": parse_int("TE", 0),
        "K": parse_int("K", 0),
        "DEF": parse_int("DEF", 0),
        "FLEX": parse_int("FLEX", 0),
    }
    starter_limits = {
        "QB": qb,
        "RB": rb,
        "WR": wr,
        "TE": te,
        "K": k,
        "DEF": defense,
        "FLEX": flex,
    }
    for position, starter_count in starter_counts.items():
        if starter_count > starter_limits[position]:
            raise HTTPException(
                status_code=400,
                detail=f"{position} starter count cannot exceed MAX_{position}.",
            )

    allow_partial = parse_int("ALLOW_PARTIAL_LINEUP", 0)
    if allow_partial not in (0, 1):
        raise HTTPException(
            status_code=400,
            detail="ALLOW_PARTIAL_LINEUP must be 0 or 1.",
        )

    require_submit = parse_int("REQUIRE_WEEKLY_SUBMIT", 1)
    if require_submit not in (0, 1):
        raise HTTPException(
            status_code=400,
            detail="REQUIRE_WEEKLY_SUBMIT must be 0 or 1.",
        )

# --- Endpoints ---

@router.get("/", response_model=List[LeagueSummary])
def get_leagues(db: Session = Depends(get_db)):
    """List all available leagues."""
    leagues = db.query(models.League).all()
    summaries: list[LeagueSummary] = []
    for league in leagues:
        settings = (
            db.query(models.LeagueSettings)
            .filter(models.LeagueSettings.league_id == league.id)
            .first()
        )
        summaries.append(
            LeagueSummary(
                id=league.id,
                name=league.name,
                draft_status=league.draft_status or "PRE_DRAFT",
                divisions_enabled=bool(settings.divisions_enabled) if settings else False,
                division_count=settings.division_count if settings else None,
                division_config_status=settings.division_config_status if settings else None,
                requires_reseed_review=bool(settings.division_needs_reseed) if settings else False,
            )
        )
    return summaries

# --- NEW: GET /league/owners?league_id= ---
# This is a GET endpoint to match the frontend call, but is defined here for convenience.


def fetch_league_owners_data(league_id: int, db: Session, group_by_division: bool = False) -> List[Dict[str, Any]]:
    """
    Internal helper: fetch league owner stats without auth checks.
    Used by the /leagues/owners endpoint (after auth) and by playoffs.py directly.
    """
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    owners = db.query(models.User).filter(
        models.User.league_id == league_id,
        ~models.User.username.like("hist_%"),
    ).all()

    # Build a map from user id to division_id once to avoid per-matchup queries
    # inside calc_stats (which would otherwise cause an N+1 pattern).
    user_division_map: dict[int, int | None] = {o.id: o.division_id for o in owners}

    def calc_stats(owner: models.User) -> dict:
        """Return aggregated W/L/T plus display-only division wins and points."""
        owner_id = owner.id
        w = l = t = pf = pa = division_wins = 0
        matches = db.query(models.Matchup).filter(
            models.Matchup.league_id == league_id,
            or_(
                models.Matchup.home_team_id == owner_id,
                models.Matchup.away_team_id == owner_id,
            ),
        ).all()
        for m in matches:
            # skip not-yet-played
            if not m.is_completed:
                continue
            if m.home_team_id == owner_id:
                score = m.home_score or 0
                opp = m.away_score or 0
            else:
                score = m.away_score or 0
                opp = m.home_score or 0
            pf += score
            pa += opp
            if score > opp:
                w += 1
            elif score < opp:
                l += 1
            else:
                t += 1

            # Display-only stat for UI (not part of tiebreak chain).
            if owner.division_id and m.home_team_id and m.away_team_id:
                home_div = user_division_map.get(m.home_team_id)
                away_div = user_division_map.get(m.away_team_id)
                if home_div and away_div and home_div == away_div:
                    if score > opp:
                        division_wins += 1

        games_played = w + l + t
        overall_record = {
            "wins": w,
            "losses": l,
            "ties": t,
            "win_pct": round((w / games_played), 4) if games_played else 0.0,
        }
        return {
            "wins": w,
            "losses": l,
            "ties": t,
            "pf": pf,
            "pa": pa,
            "points_for": pf,
            "points_against": pa,
            "win_pct": overall_record["win_pct"],
            "division_wins": division_wins,
            "overall_record": overall_record,
        }

    owners_data = []
    for o in owners:
        stats = calc_stats(o)
        owners_data.append(
            {
                "id": o.id,
                "username": o.username,
                "email": o.email,
                "team_name": o.team_name,
                "division_id": o.division_id,
                "division_name": o.division_obj.name if o.division_obj else None,
                "division": {
                    "id": o.division_id,
                    "name": o.division_obj.name if o.division_obj else None,
                    "order_index": o.division_obj.order_index if o.division_obj else None,
                },
                "standings_metrics": {
                    "overall_wins": stats["wins"],
                    "division_wins": stats["division_wins"],
                    "points_for": stats["pf"],
                    "points_against": stats["pa"],
                    "overall_record": stats["overall_record"],
                },
                "tiebreak_context": {
                    "applied_chain": [
                        "overall_record",
                        "head_to_head",
                        "points_for",
                        "points_against",
                        "random_draw",
                    ],
                    "rank_reason": "overall_record",
                },
                **stats,
            }
        )

    # optionally group by division as secondary sort
    if group_by_division:
        owners_data.sort(
            key=lambda o: (o.get("division_id") or 0, *owner_standings_sort_key(o))
        )
    else:
        owners_data.sort(key=owner_standings_sort_key)
    return owners_data


@router.get("/owners")
def get_league_owners(league_id: int = Query(...),
                      group_by_division: bool = Query(False),
                      current_user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    if not current_user.is_superuser and int(current_user.league_id or 0) != int(league_id):
        logger.warning(
            "League owner listing denied due to league mismatch (user_id=%s user_league_id=%s requested_league_id=%s)",
            current_user.id,
            current_user.league_id,
            league_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Access denied: user is not mapped to the requested league.",
                "error_code": "LEAGUE_MAPPING_MISMATCH",
                "user_league_id": current_user.league_id,
                "requested_league_id": league_id,
            },
        )
    return fetch_league_owners_data(league_id=league_id, db=db, group_by_division=group_by_division)

# --- NEW: GET /leagues/{league_id} ---
@router.get("/{league_id}", response_model=LeagueSummary)
def get_league_by_id(league_id: int, db: Session = Depends(get_db)):
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league.id).first()
    return LeagueSummary(
        id=league.id,
        name=league.name,
        draft_status=league.draft_status or "PRE_DRAFT",
        divisions_enabled=bool(settings.divisions_enabled) if settings else False,
        division_count=settings.division_count if settings else None,
        division_config_status=settings.division_config_status if settings else None,
        requires_reseed_review=bool(settings.division_needs_reseed) if settings else False,
    )

@router.get("/{league_id}/news", response_model=List[LeagueNewsItem])
def get_league_news(
    league_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    session_key = f"LEAGUE_{league_id}"
    picks = (
        db.query(models.DraftPick)
        .join(models.User, models.DraftPick.owner_id == models.User.id)
        .filter(
            or_(
                models.DraftPick.league_id == league_id,
                models.DraftPick.session_id == session_key,
            ),
            ~models.User.username.like("hist_%"),
        )
        .order_by(desc(models.DraftPick.id))
        .limit(limit)
        .all()
    )

    items: List[LeagueNewsItem] = []
    for pick in picks:
        owner_name = pick.owner.username if pick.owner else "Unknown Owner"
        # Defense-in-depth: skip historical MFL-import users (primary guard is the join filter above)
        if owner_name.startswith("hist_"):
            continue
        player_name = _normalize_player_name(pick.player.name) if pick.player else "Unknown Player"
        timestamp = pick.timestamp or "Just now"
        items.append(
            LeagueNewsItem(
                type="info",
                title=f"{owner_name} drafted {player_name} for ${pick.amount}",
                timestamp=timestamp,
            )
        )

    return items

@router.post("/", response_model=LeagueSummary)
def create_league(league_data: LeagueCreate, db: Session = Depends(get_db)):
    """Create a new league + Default Scoring Rules + Default Settings."""
    # 1. Check if name exists
    existing = db.query(models.League).filter(models.League.name == league_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="League name already taken")
    
    # 2. Create League
    new_league = models.League(name=league_data.name)
    db.add(new_league)
    db.commit()
    db.refresh(new_league)
    
    # 3. Create Default Settings (NEW)
    default_settings = models.LeagueSettings(league_id=new_league.id)
    db.add(default_settings)

    # 4. Create Default Scoring Rules
    default_rules = [
        models.ScoringRule(
            league_id=new_league.id,
            category="passing",
            event_name="Passing TD",
            description="Passing TD",
            range_min=0,
            range_max=9999,
            point_value=4.0,
            calculation_type="flat_bonus",
            applicable_positions=["QB","RB","WR","TE"],
        ),
        models.ScoringRule(
            league_id=new_league.id,
            category="passing",
            event_name="Interception",
            description="Interception",
            range_min=0,
            range_max=9999,
            point_value=-2.0,
            calculation_type="flat_bonus",
            applicable_positions=["QB","RB","WR","TE"],
        ),
        models.ScoringRule(
            league_id=new_league.id,
            category="rushing",
            event_name="Rushing TD",
            description="Rushing TD",
            range_min=0,
            range_max=9999,
            point_value=6.0,
            calculation_type="flat_bonus",
            applicable_positions=["QB","RB","WR","TE"],
        ),
        models.ScoringRule(
            league_id=new_league.id,
            category="receiving",
            event_name="Reception (PPR)",
            description="Reception (PPR)",
            range_min=0,
            range_max=9999,
            point_value=1.0,
            calculation_type="flat_bonus",
            applicable_positions=["QB","RB","WR","TE"],
        ),
    ]
    db.add_all(default_rules)
    db.commit()

    return LeagueSummary(
        id=new_league.id,
        name=new_league.name,
        draft_status=new_league.draft_status or "PRE_DRAFT",
    )

@router.post("/join")
def join_league(league_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Let a user join a specific league."""
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    
    current_user.league_id = league_id
    db.commit()
    return {"message": f"Welcome to {league.name}!"}

# --- NEW: LEAGUE SETTINGS ENDPOINTS ---

# --- Waiver budget endpoint ---
@router.get("/{league_id}/waiver-budgets", response_model=List[WaiverBudgetSchema])
def get_waiver_budgets(league_id: int, db: Session = Depends(get_db)):
    has_faab_ledger = (
        db.query(models.EconomicLedger.id)
        .filter(
            models.EconomicLedger.league_id == league_id,
            models.EconomicLedger.currency_type == "FAAB",
        )
        .first()
        is not None
    )

    if has_faab_ledger:
        users = db.query(models.User).filter(
            models.User.league_id == league_id,
            ~models.User.username.like("hist_%"),
        ).all()
        legacy_records = (
            db.query(models.WaiverBudget)
            .filter(models.WaiverBudget.league_id == league_id)
            .all()
        )
        legacy_by_owner = {r.owner_id: r for r in legacy_records}

        response: list[WaiverBudgetSchema] = []
        for user in users:
            incoming_total = (
                db.query(func.coalesce(func.sum(models.EconomicLedger.amount), 0))
                .filter(
                    models.EconomicLedger.league_id == league_id,
                    models.EconomicLedger.currency_type == "FAAB",
                    models.EconomicLedger.to_owner_id == user.id,
                )
                .scalar()
            )

            owner_has_credit_history = int(incoming_total or 0) > 0
            legacy = legacy_by_owner.get(user.id)
            if not owner_has_credit_history and legacy is not None:
                response.append(
                    WaiverBudgetSchema(
                        owner_id=legacy.owner_id,
                        starting_budget=int(legacy.starting_budget or 0),
                        remaining_budget=int(legacy.remaining_budget or 0),
                        spent_budget=int(legacy.spent_budget or 0),
                    )
                )
                continue

            starting_budget = (
                db.query(func.coalesce(func.sum(models.EconomicLedger.amount), 0))
                .filter(
                    models.EconomicLedger.league_id == league_id,
                    models.EconomicLedger.currency_type == "FAAB",
                    models.EconomicLedger.to_owner_id == user.id,
                    models.EconomicLedger.from_owner_id.is_(None),
                )
                .scalar()
            )
            spent_budget = (
                db.query(func.coalesce(func.sum(models.EconomicLedger.amount), 0))
                .filter(
                    models.EconomicLedger.league_id == league_id,
                    models.EconomicLedger.currency_type == "FAAB",
                    models.EconomicLedger.from_owner_id == user.id,
                    models.EconomicLedger.to_owner_id.is_(None),
                )
                .scalar()
            )

            response.append(
                WaiverBudgetSchema(
                    owner_id=user.id,
                    starting_budget=int(starting_budget or 0),
                    remaining_budget=owner_balance(
                        db,
                        league_id=league_id,
                        owner_id=user.id,
                        currency_type="FAAB",
                    ),
                    spent_budget=int(spent_budget or 0),
                )
            )

        return response

    records = (
        db.query(models.WaiverBudget)
        .filter(models.WaiverBudget.league_id == league_id)
        .all()
    )
    return [
        WaiverBudgetSchema(
            owner_id=r.owner_id,
            starting_budget=r.starting_budget,
            remaining_budget=r.remaining_budget,
            spent_budget=r.spent_budget,
        )
        for r in records
    ]
@router.get("/{league_id}/settings", response_model=LeagueConfigFull)
def get_league_settings(league_id: int, db: Session = Depends(get_db)):
    # Sanity: if the database is missing the column added by runtime schema,
    # attempt to add it before the query.
    try:
        db.execute("ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS starting_slots JSON DEFAULT '{}'::json")
        db.execute("ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS future_draft_cap INTEGER DEFAULT 0")
        db.commit()
    except Exception:
        db.rollback()

    # 1. Get Settings (Roster, Cap)
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league_id).first()
    if not settings:
        # Provide robust defaults for all required fields
        settings = models.LeagueSettings(
            league_id=league_id,
            roster_size=14,
            salary_cap=200,
            starting_slots={
                "QB": 1,
                "RB": 2,
                "WR": 2,
                "TE": 1,
                "K": 1,
                "DEF": 1,
                "FLEX": 1,
                "ACTIVE_ROSTER_SIZE": 9,
                "MAX_QB": 3,
                "MAX_RB": 5,
                "MAX_WR": 5,
                "MAX_TE": 3,
                "MAX_K": 1,
                "MAX_DEF": 1,
                "ALLOW_PARTIAL_LINEUP": 0,
                "REQUIRE_WEEKLY_SUBMIT": 1,
            },
            waiver_deadline=None,
            starting_waiver_budget=100,
            waiver_system='FAAB',
            waiver_tiebreaker='standings',
            trade_deadline=None
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    # 2. Get Scoring Rules (Points)
    rules = db.query(models.ScoringRule).filter(models.ScoringRule.league_id == league_id).all()
    
    # --- SELF-HEALING: If no rules exist, create them now! ---
    if not rules:
        default_rules = [
            models.ScoringRule(
                league_id=league_id,
                category="passing",
                event_name="Passing TD",
                description="Passing TD",
                range_min=0,
                range_max=9999,
                point_value=4.0,
                calculation_type="flat_bonus",
                applicable_positions=["QB","RB","WR","TE"],
            ),
            models.ScoringRule(
                league_id=league_id,
                category="passing",
                event_name="Interception",
                description="Interception",
                range_min=0,
                range_max=9999,
                point_value=-2.0,
                calculation_type="flat_bonus",
                applicable_positions=["QB","RB","WR","TE"],
            ),
            models.ScoringRule(
                league_id=league_id,
                category="rushing",
                event_name="Rushing TD",
                description="Rushing TD",
                range_min=0,
                range_max=9999,
                point_value=6.0,
                calculation_type="flat_bonus",
                applicable_positions=["QB","RB","WR","TE"],
            ),
            models.ScoringRule(
                league_id=league_id,
                category="receiving",
                event_name="Reception (PPR)",
                description="Reception (PPR)",
                range_min=0,
                range_max=9999,
                point_value=1.0,
                calculation_type="flat_bonus",
                applicable_positions=["QB","RB","WR","TE"],
            ),
            models.ScoringRule(
                league_id=league_id,
                category="kicking",
                event_name="Field Goal Made",
                description="Field Goal Made",
                range_min=0,
                range_max=9999,
                point_value=3.0,
                calculation_type="flat_bonus",
                applicable_positions=["ALL"],
            ),
            models.ScoringRule(
                league_id=league_id,
                category="defense",
                event_name="Sack",
                description="Sack",
                range_min=0,
                range_max=9999,
                point_value=1.0,
                calculation_type="flat_bonus",
                applicable_positions=["ALL"],
            ),
        ]
        db.add_all(default_rules)
        db.commit()
        # Fetch them again so they appear immediately
        rules = db.query(models.ScoringRule).filter(models.ScoringRule.league_id == league_id).all()
    
    # 3. Combine them
    return LeagueConfigFull(
        roster_size=settings.roster_size,
        salary_cap=settings.salary_cap,
        starting_slots=settings.starting_slots or {},
        waiver_deadline=settings.waiver_deadline,
        starting_waiver_budget=settings.starting_waiver_budget,
        waiver_system=settings.waiver_system,
        waiver_tiebreaker=settings.waiver_tiebreaker,
        draft_year=settings.draft_year,
        scoring_rules=[
            ScoringRuleSchema(
                category=r.category or "",
                event_name=r.event_name or "",
                description=r.description,
                range_min=float(r.range_min) if r.range_min is not None else 0.0,
                range_max=float(r.range_max) if r.range_max is not None else 0.0,
                # some older rows may have NULL point_value; treat as 0
                point_value=float(r.point_value or 0),
                calculation_type=r.calculation_type,
                applicable_positions=r.applicable_positions or [],
            )
            for r in rules
        ]
    )

@router.put("/{league_id}/settings")
def update_league_settings(
    league_id: int, 
    config: LeagueConfigFull, 
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    normalized_slots = canonicalize_lineup_slots(config.starting_slots)
    config = config.model_copy(update={"starting_slots": normalized_slots})

    settings_payload = {
        "roster_size": config.roster_size,
        "salary_cap": config.salary_cap,
        "starting_slots": config.starting_slots,
        "waiver_deadline": config.waiver_deadline,
        "starting_waiver_budget": config.starting_waiver_budget,
        "waiver_system": config.waiver_system,
        "waiver_tiebreaker": config.waiver_tiebreaker,
        "trade_deadline": config.trade_deadline,
        "draft_year": config.draft_year,
        "scoring_rules": [rule.model_dump() for rule in config.scoring_rules],
    }

    boundary_report = validate_league_settings_boundary(settings_payload)
    if not boundary_report.valid:
        error_msg = format_validation_errors(boundary_report.errors)
        raise HTTPException(status_code=400, detail=error_msg)

    dynamic_report = validate_league_settings_dynamic_rules(settings_payload)
    if not dynamic_report.valid:
        error_msg = format_validation_errors(dynamic_report.errors)
        raise HTTPException(status_code=400, detail=error_msg)

    validate_lineup_rules(config)

    # 1. Update Settings
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league_id).first()
    if not settings:
        settings = models.LeagueSettings(league_id=league_id)
        db.add(settings)
        db.flush()

    settings.roster_size = config.roster_size
    settings.salary_cap = config.salary_cap
    settings.starting_slots = config.starting_slots
    settings.waiver_deadline = config.waiver_deadline
    settings.starting_waiver_budget = config.starting_waiver_budget
    settings.waiver_system = config.waiver_system
    settings.waiver_tiebreaker = config.waiver_tiebreaker
    settings.trade_deadline = getattr(config, 'trade_deadline', None)
    if config.draft_year is not None:
        settings.draft_year = config.draft_year
    
    # 2. Update Rules (Nuclear Option: Delete old, add new)
    # This is the easiest way to handle edits/deletes without complex logic
    db.query(models.ScoringRule).filter(models.ScoringRule.league_id == league_id).delete()
    
    new_rules = []
    for r in config.scoring_rules:
        new_rules.append(models.ScoringRule(
            league_id=league_id,
            category=r.category,
            event_name=r.event_name,
            description=r.description,
            range_min=r.range_min,
            range_max=r.range_max,
            point_value=r.point_value,
            calculation_type=r.calculation_type,
            applicable_positions=r.applicable_positions,
        ))
    db.add_all(new_rules)
    
    db.commit()
    return {"message": "League configuration saved!"}

# --- NEW: SET LEAGUE DRAFT YEAR ---
@router.post("/{league_id}/draft-year")
def set_league_draft_year(
    league_id: int,
    payload: Dict[str, int],
    current_user: models.User = Depends(check_is_commissioner),
    db: Session = Depends(get_db)
):
    year = payload.get("year")
    if not year:
        raise HTTPException(status_code=400, detail="year is required")

    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league_id).first()
    if not settings:
        settings = models.LeagueSettings(league_id=league_id)
        db.add(settings)

    settings.draft_year = year
    db.commit()
    return {"message": "Draft year updated", "draft_year": settings.draft_year}

# --- NEW: GET/SET DRAFT BUDGETS ---
@router.get("/{league_id}/budgets")
def get_league_budgets(
    league_id: int,
    year: int = Query(...),
    db: Session = Depends(get_db)
):
    owners = db.query(models.User).filter(
        models.User.league_id == league_id,
        ~models.User.username.like("hist_%"),
    ).all()
    has_draft_ledger = (
        db.query(models.EconomicLedger.id)
        .filter(
            models.EconomicLedger.league_id == league_id,
            models.EconomicLedger.currency_type == "DRAFT_DOLLARS",
            models.EconomicLedger.season_year == year,
        )
        .first()
        is not None
    )

    legacy_budget_map: dict[int, int | None] = {}
    try:
        budgets = db.query(models.DraftBudget).filter(
            models.DraftBudget.league_id == league_id,
            models.DraftBudget.year == year
        ).all()
        legacy_budget_map = {b.owner_id: b.total_budget for b in budgets}
    except Exception:
        # if the budgets table doesn't exist yet (migration not applied)
        budgets = []

    if has_draft_ledger:
        rows = []
        for owner in owners:
            if owner_has_incoming_credits(
                db,
                league_id=league_id,
                owner_id=owner.id,
                currency_type="DRAFT_DOLLARS",
                season_year=year,
            ):
                total_budget = owner_draft_budget_total(
                    db,
                    league_id=league_id,
                    owner_id=owner.id,
                    season_year=year,
                    include_keeper_locks=False,
                )
            else:
                total_budget = legacy_budget_map.get(owner.id)

            rows.append(
                {
                    "owner_id": owner.id,
                    "username": owner.username,
                    "team_name": owner.team_name,
                    "total_budget": total_budget,
                }
            )
        return rows

    return [
        {
            "owner_id": owner.id,
            "username": owner.username,
            "team_name": owner.team_name,
            "total_budget": legacy_budget_map.get(owner.id),
        }
        for owner in owners
    ]

@router.post("/{league_id}/budgets")
def update_league_budgets(
    league_id: int,
    payload: BudgetUpdateRequest,
    current_user: models.User = Depends(check_is_commissioner),
    db: Session = Depends(get_db)
):
    year = payload.year
    for entry in payload.budgets:
        current_total = 0
        has_credits = owner_has_incoming_credits(
            db,
            league_id=league_id,
            owner_id=entry.owner_id,
            currency_type="DRAFT_DOLLARS",
            season_year=year,
        )
        if has_credits:
            current_total = owner_draft_budget_total(
                db,
                league_id=league_id,
                owner_id=entry.owner_id,
                season_year=year,
                include_keeper_locks=False,
            )

        existing = db.query(models.DraftBudget).filter(
            models.DraftBudget.league_id == league_id,
            models.DraftBudget.owner_id == entry.owner_id,
            models.DraftBudget.year == year
        ).first()

        if not has_credits and existing and existing.total_budget is not None:
            current_total = int(existing.total_budget)

        target_total = int(entry.total_budget)
        delta = target_total - int(current_total)
        if delta > 0:
            record_ledger_entry(
                db,
                league_id=league_id,
                season_year=year,
                currency_type="DRAFT_DOLLARS",
                amount=int(delta),
                from_owner_id=None,
                to_owner_id=entry.owner_id,
                transaction_type="SEASON_ALLOCATION",
                reference_type="LEAGUE_BUDGETS",
                reference_id=f"{league_id}:{year}:{entry.owner_id}",
                notes="commissioner budget set increase",
                created_by_user_id=current_user.id,
            )
        elif delta < 0:
            record_ledger_entry(
                db,
                league_id=league_id,
                season_year=year,
                currency_type="DRAFT_DOLLARS",
                amount=abs(int(delta)),
                from_owner_id=entry.owner_id,
                to_owner_id=None,
                transaction_type="COMMISSIONER_ADJUSTMENT_DEBIT",
                reference_type="LEAGUE_BUDGETS",
                reference_id=f"{league_id}:{year}:{entry.owner_id}",
                notes="commissioner budget set decrease",
                created_by_user_id=current_user.id,
            )

        if existing:
            existing.total_budget = target_total
        else:
            db.add(models.DraftBudget(
                league_id=league_id,
                owner_id=entry.owner_id,
                year=year,
                total_budget=target_total
            ))

    db.commit()
    return {"message": "Budgets updated", "year": year}


@router.get("/{league_id}/ledger/statement", response_model=LedgerStatementSchema)
def get_ledger_statement(
    league_id: int,
    owner_id: Optional[int] = Query(None),
    currency_type: Optional[str] = Query(None),
    season_year: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.league_id != league_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: user is not in this league.",
        )

    target_owner_id = owner_id if owner_id is not None else current_user.id
    if not current_user.is_commissioner and target_owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: owner can only view their own ledger.",
        )

    target_owner = (
        db.query(models.User)
        .filter(models.User.id == target_owner_id, models.User.league_id == league_id)
        .first()
    )
    if not target_owner:
        raise HTTPException(status_code=404, detail="Owner not found in league")

    query = db.query(models.EconomicLedger).filter(
        models.EconomicLedger.league_id == league_id,
        or_(
            models.EconomicLedger.to_owner_id == target_owner_id,
            models.EconomicLedger.from_owner_id == target_owner_id,
        ),
    )

    if currency_type:
        query = query.filter(models.EconomicLedger.currency_type == currency_type)
    if season_year is not None:
        query = query.filter(models.EconomicLedger.season_year == season_year)

    entries = (
        query.order_by(models.EconomicLedger.created_at.desc(), models.EconomicLedger.id.desc())
        .limit(limit)
        .all()
    )

    balance_query = db.query(func.coalesce(func.sum(
        case(
            (models.EconomicLedger.to_owner_id == target_owner_id, models.EconomicLedger.amount),
            else_=0,
        ) - case(
            (models.EconomicLedger.from_owner_id == target_owner_id, models.EconomicLedger.amount),
            else_=0,
        )
    ), 0)).filter(
        models.EconomicLedger.league_id == league_id,
        or_(
            models.EconomicLedger.to_owner_id == target_owner_id,
            models.EconomicLedger.from_owner_id == target_owner_id,
        ),
    )
    if currency_type:
        balance_query = balance_query.filter(models.EconomicLedger.currency_type == currency_type)
    if season_year is not None:
        balance_query = balance_query.filter(models.EconomicLedger.season_year == season_year)

    balance = int(balance_query.scalar() or 0)

    payload_entries = []
    for entry in entries:
        if entry.to_owner_id == target_owner_id and entry.from_owner_id == target_owner_id:
            direction = "TRANSFER"
        elif entry.to_owner_id == target_owner_id:
            direction = "CREDIT"
        elif entry.from_owner_id == target_owner_id:
            direction = "DEBIT"
        else:
            direction = "NEUTRAL"

        payload_entries.append(
            LedgerEntrySchema(
                id=entry.id,
                created_at=entry.created_at.isoformat() if entry.created_at else None,
                season_year=entry.season_year,
                currency_type=entry.currency_type,
                transaction_type=entry.transaction_type,
                amount=int(entry.amount or 0),
                from_owner_id=entry.from_owner_id,
                to_owner_id=entry.to_owner_id,
                direction=direction,
                reference_type=entry.reference_type,
                reference_id=entry.reference_id,
                notes=entry.notes,
            )
        )

    return LedgerStatementSchema(
        league_id=league_id,
        owner_id=target_owner_id,
        currency_type=currency_type,
        season_year=season_year,
        balance=balance,
        entry_count=len(payload_entries),
        entries=payload_entries,
    )

# --- NEW: USER MANAGEMENT ENDPOINTS ---

@router.post("/{league_id}/members")
def add_league_member(
    league_id: int, 
    request: AddMemberRequest, 
    current_user: models.User = Depends(check_is_commissioner),
    db: Session = Depends(get_db)
):
    """Move a specific user into this league."""
    if current_user.league_id != league_id:
        raise HTTPException(status_code=403, detail="Commissioner can only manage members in their league")

    user = db.query(models.User).filter(models.User.username == request.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.league_id = league_id
    db.commit()
    return {"message": f"{user.username} added to the league!"}

@router.delete("/{league_id}/members/{user_id}")
def remove_league_member(
    league_id: int, 
    user_id: int, 
    current_user: models.User = Depends(check_is_commissioner),
    db: Session = Depends(get_db)
):
    """Kick a user out of the league (Make them a Free Agent)."""
    if current_user.league_id != league_id:
        raise HTTPException(status_code=403, detail="Commissioner can only manage members in their league")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.league_id != league_id:
         raise HTTPException(status_code=400, detail="User is not in this league.")

    user.league_id = None  # Reset to NULL
    db.commit()
    return {"message": "User removed from league."}

# --- NEW: CREATE OWNER ENDPOINT ---
@router.post("/owners")
def create_owner(
    request: AddMemberRequest, 
    current_user: models.User = Depends(check_is_commissioner),
    db: Session = Depends(get_db)
):
    """Invite a new user with an auto-generated 8-char password."""

    if request.league_id and request.league_id != current_user.league_id:
        raise HTTPException(status_code=403, detail="Commissioner can only add owners to their league")
    
    # 1. Check if username exists
    if db.query(models.User).filter(models.User.username == request.username).first():
        raise HTTPException(status_code=400, detail="Username taken.")
    
    # 2. Check if email exists (if provided)
    if request.email and db.query(models.User).filter(models.User.email == request.email).first():
        raise HTTPException(status_code=400, detail="Email already in use.")

    # 3. Generate 8-Digit Random Password
    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for i in range(8))
    
    # 4. Hash & Save
    from core.security import get_password_hash
    hashed_pw = get_password_hash(temp_password)
    
    owner_limit = None
    if request.league_id:
        league_settings = db.query(models.LeagueSettings).filter(
            models.LeagueSettings.league_id == request.league_id
        ).first()
        if league_settings and league_settings.starting_slots:
            owner_limit = int(
                league_settings.starting_slots.get("OWNER_LIMIT", 0) or 0
            )
        if owner_limit and owner_limit > 0:
            current_count = db.query(models.User).filter(
                models.User.league_id == request.league_id,
                models.User.username.not_in(["Free Agent", "Obsolete"]),
            ).count()
            if current_count >= owner_limit:
                raise HTTPException(
                    status_code=400,
                    detail=f"League owner limit reached ({owner_limit}).",
                )

    # Create the user and auto-assign to league when provided
    new_user = models.User(
        username=request.username, 
        email=request.email,
        hashed_password=hashed_pw,
        league_id=request.league_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 5. Send the Email (or print to console)
    if request.email:
        send_invite_email(
            request.email,
            request.username,
            temp_password,
            request.league_id,
        )
    else:
        # Fallback if no email provided: print to console anyway
        print(f"User created without email. Temp Password: {temp_password}")
    
    return {
        "message": f"Invite sent to {request.email or 'Console'}!",
        "league_id": request.league_id,
        # In production, DO NOT return the password here. For now, it helps debugging.
        "debug_password": temp_password 
    }


# --- HISTORICAL RECORDS ENDPOINTS ---

class HistoricalRecordSchema(BaseModel):
    record_json: Dict[str, Any]
    season: Optional[int] = None


class HistoricalRecordsResponse(BaseModel):
    dataset_key: str
    league_id: str
    records: List[Dict[str, Any]]
    count: int


@router.get("/{league_id}/history/champions")
def get_league_champions(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get all league champions through history."""
    if not current_user.is_superuser and int(current_user.league_id or 0) != int(league_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    mfl_league_id = str(league_id)
    records = db.query(models.MflHtmlRecordFact).filter(
        models.MflHtmlRecordFact.dataset_key == "html_league_champions_normalized",
        models.MflHtmlRecordFact.league_id == mfl_league_id,
    ).order_by(desc(models.MflHtmlRecordFact.season)).all()
    
    data = [r.record_json for r in records]
    return HistoricalRecordsResponse(
        dataset_key="html_league_champions_normalized",
        league_id=mfl_league_id,
        records=data,
        count=len(data),
    )


@router.get("/{league_id}/history/awards")
def get_league_awards(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get all league awards through history."""
    if not current_user.is_superuser and int(current_user.league_id or 0) != int(league_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    mfl_league_id = str(league_id)
    records = db.query(models.MflHtmlRecordFact).filter(
        models.MflHtmlRecordFact.dataset_key == "html_league_awards_normalized",
        models.MflHtmlRecordFact.league_id == mfl_league_id,
    ).order_by(desc(models.MflHtmlRecordFact.season)).all()
    
    data = [r.record_json for r in records]
    return HistoricalRecordsResponse(
        dataset_key="html_league_awards_normalized",
        league_id=mfl_league_id,
        records=data,
        count=len(data),
    )


@router.get("/{league_id}/history/records/franchise")
def get_franchise_records(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get franchise single-game scoring records."""
    if not current_user.is_superuser and int(current_user.league_id or 0) != int(league_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    mfl_league_id = str(league_id)
    records = db.query(models.MflHtmlRecordFact).filter(
        models.MflHtmlRecordFact.dataset_key == "html_franchise_records_normalized",
        models.MflHtmlRecordFact.league_id == mfl_league_id,
    ).order_by(desc(models.MflHtmlRecordFact.record_json['record_year'].astext)).all()
    
    data = [r.record_json for r in records]
    return HistoricalRecordsResponse(
        dataset_key="html_franchise_records_normalized",
        league_id=mfl_league_id,
        records=data,
        count=len(data),
    )


@router.get("/{league_id}/history/records/player")
def get_player_records(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get top player single-week scoring records."""
    if not current_user.is_superuser and int(current_user.league_id or 0) != int(league_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    mfl_league_id = str(league_id)
    records = db.query(models.MflHtmlRecordFact).filter(
        models.MflHtmlRecordFact.dataset_key == "html_player_records_normalized",
        models.MflHtmlRecordFact.league_id == mfl_league_id,
    ).order_by(desc(models.MflHtmlRecordFact.record_json['record_year'].astext)).limit(100).all()
    
    data = [r.record_json for r in records]
    return HistoricalRecordsResponse(
        dataset_key="html_player_records_normalized",
        league_id=mfl_league_id,
        records=data,
        count=len(data),
    )


@router.get("/{league_id}/history/records/match")
def get_matchup_records(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get highest-scoring matchups and greatest comebacks."""
    if not current_user.is_superuser and int(current_user.league_id or 0) != int(league_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    mfl_league_id = str(league_id)
    records = db.query(models.MflHtmlRecordFact).filter(
        models.MflHtmlRecordFact.dataset_key == "html_matchup_records_normalized",
        models.MflHtmlRecordFact.league_id == mfl_league_id,
    ).order_by(desc(models.MflHtmlRecordFact.record_json['record_year'].astext)).limit(100).all()
    
    data = [r.record_json for r in records]
    return HistoricalRecordsResponse(
        dataset_key="html_matchup_records_normalized",
        league_id=mfl_league_id,
        records=data,
        count=len(data),
    )


@router.get("/{league_id}/history/records/all-time-series")
def get_all_time_series_records(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get head-to-head all-time series records between managers."""
    if not current_user.is_superuser and int(current_user.league_id or 0) != int(league_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    mfl_league_id = str(league_id)
    records = db.query(models.MflHtmlRecordFact).filter(
        models.MflHtmlRecordFact.dataset_key == "html_all_time_series_normalized",
        models.MflHtmlRecordFact.league_id == mfl_league_id,
    ).order_by(desc(models.MflHtmlRecordFact.record_json['series_season'].astext)).limit(100).all()
    
    data = [r.record_json for r in records]
    return HistoricalRecordsResponse(
        dataset_key="html_all_time_series_normalized",
        league_id=mfl_league_id,
        records=data,
        count=len(data),
    )


@router.get("/{league_id}/history/records/season")
def get_season_records(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get best season records (wins, points for/against)."""
    if not current_user.is_superuser and int(current_user.league_id or 0) != int(league_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    mfl_league_id = str(league_id)
    records = db.query(models.MflHtmlRecordFact).filter(
        models.MflHtmlRecordFact.dataset_key == "html_season_records_normalized",
        models.MflHtmlRecordFact.league_id == mfl_league_id,
    ).order_by(desc(models.MflHtmlRecordFact.record_json['record_year'].astext)).all()
    
    data = [r.record_json for r in records]
    return HistoricalRecordsResponse(
        dataset_key="html_season_records_normalized",
        league_id=mfl_league_id,
        records=data,
        count=len(data),
    )


@router.get("/{league_id}/history/records/career")
def get_career_records(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get career aggregate records across league history."""
    if not current_user.is_superuser and int(current_user.league_id or 0) != int(league_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    mfl_league_id = str(league_id)
    records = db.query(models.MflHtmlRecordFact).filter(
        models.MflHtmlRecordFact.dataset_key == "html_career_records_normalized",
        models.MflHtmlRecordFact.league_id == mfl_league_id,
    ).order_by(desc(models.MflHtmlRecordFact.record_json['wins'].astext.cast(func.numeric))).all()
    
    data = [r.record_json for r in records]
    return HistoricalRecordsResponse(
        dataset_key="html_career_records_normalized",
        league_id=mfl_league_id,
        records=data,
        count=len(data),
    )


@router.get("/{league_id}/history/records/streaks")
def get_record_streaks(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get notable win/loss streaks through history."""
    if not current_user.is_superuser and int(current_user.league_id or 0) != int(league_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    mfl_league_id = str(league_id)
    records = db.query(models.MflHtmlRecordFact).filter(
        models.MflHtmlRecordFact.dataset_key == "html_record_streaks_normalized",
        models.MflHtmlRecordFact.league_id == mfl_league_id,
    ).order_by(desc(models.MflHtmlRecordFact.record_json['record_year'].astext)).limit(100).all()
    
    data = [r.record_json for r in records]
    return HistoricalRecordsResponse(
        dataset_key="html_record_streaks_normalized",
        league_id=mfl_league_id,
        records=data,
        count=len(data),
    )


@router.put("/owners/{owner_id}")
def update_owner(
    owner_id: int,
    request: AddMemberRequest,
    current_user: models.User = Depends(check_is_commissioner),
    db: Session = Depends(get_db),
):
    owner = db.query(models.User).filter(models.User.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    if request.username != owner.username:
        existing = db.query(models.User).filter(models.User.username == request.username).first()
        if existing and existing.id != owner.id:
            raise HTTPException(status_code=400, detail="Username taken.")
        owner.username = request.username

    if request.email != owner.email:
        if request.email:
            existing_email = db.query(models.User).filter(models.User.email == request.email).first()
            if existing_email and existing_email.id != owner.id:
                raise HTTPException(status_code=400, detail="Email already in use.")
        owner.email = request.email

    db.commit()
    return {
        "message": "Owner updated.",
        "owner": {
            "id": owner.id,
            "username": owner.username,
            "email": owner.email,
            "league_id": owner.league_id,
        },
    }
# backend/routers/league.py (Add to bottom)

@router.post("/{league_id}/finalize-draft")
def finalize_draft(league_id: int, db: Session = Depends(get_db)):
    """
    Commissioner Tool: Validates rosters and locks the draft.
    """
    # 1. Get League Settings (for roster size)
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league_id).first()
    max_roster = settings.roster_size if settings else 14  # Default to 14 if missing

    # 2. Get Owners in THIS league
    owners = db.query(models.User).filter(
        models.User.league_id == league_id,
        models.User.username.not_in(["Free Agent", "Obsolete"])
    ).all()
    
    errors = []

    for owner in owners:
        picks = db.query(models.DraftPick).filter(
            models.DraftPick.owner_id == owner.id,
            models.DraftPick.league_id == league_id
        ).all()
        
        # Rule A: Check Roster Size vs League Settings
        if len(picks) < max_roster:
            errors.append(f"{owner.username} only has {len(picks)}/{max_roster} players.")
            continue

        # Rule B: Positional Check (Simple version)
        positions = set()
        for pick in picks:
            # Assuming you have a way to get player position (joined query or property)
            # For now, simplistic check if player object exists
            if pick.player: 
                pos = "DEF" if pick.player.position == "TD" else pick.player.position
                positions.add(pos)
        
        required = {"QB", "RB", "WR", "TE", "K", "DEF"}
        missing = required - positions
        
        if missing:
            errors.append(f"{owner.username} is missing: {', '.join(missing)}")

    if errors:
        return {"status": "error", "messages": errors}

    # 3. Success - In future, set league.status = 'active'
    return {"status": "success", "message": "DRAFT COMPLETE! Season is now active."}

@router.get("/players/search")
def search_players(q: str, db: Session = Depends(get_db)):
    """
    Search for players by name. 
    This is what powers the 'Global Search' and 'War Room'.
    """
    if len(q) < 2:
        return []
    
    # Search for players in relevant fantasy positions only
    allowed_positions = {"QB", "RB", "WR", "TE", "K", "DEF"}
    results = db.query(models.Player).filter(
        models.Player.name.ilike(f"%{q}%"),
        models.Player.position.in_(allowed_positions)
    ).limit(10).all()
    
    return results