# backend/routers/players.py
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from .. import models
from ..core.security import get_current_user, check_is_commissioner 
from ..services import player_service # 2.1.1 IMPORT the service logic

router = APIRouter(
    prefix="/players",
    tags=["Players"]
)

MIN_VALID_SEASON_YEAR = 2000
MAX_VALID_SEASON_YEAR = datetime.now(timezone.utc).year + 2
DEFAULT_SEASON_YEAR = datetime.now(timezone.utc).year


class PlayerSearchResult(BaseModel):
    id: int
    name: str
    position: Optional[str] = None
    nfl_team: Optional[str] = None
    adp: Optional[float] = None
    projected_points: Optional[float] = None
    gsis_id: Optional[str] = None
    espn_id: Optional[str] = None
    bye_week: Optional[int] = None


class PlayerSearchResult(BaseModel):
    id: int
    name: str
    position: Optional[str] = None
    nfl_team: Optional[str] = None
    adp: Optional[float] = None
    projected_points: Optional[float] = None
    gsis_id: Optional[str] = None
    espn_id: Optional[str] = None
    bye_week: Optional[int] = None


def _build_headshot_url(espn_id: Optional[str]) -> Optional[str]:
    if not espn_id:
        return None
    return f"https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png"


def _build_team_logo_url(team_abbr: Optional[str]) -> Optional[str]:
    if not team_abbr:
        return None

    normalized = str(team_abbr).strip().upper()
    legacy_aliases = {
        "JAC": "JAX",
        "OAK": "LV",
        "SD": "LAC",
        "STL": "LAR",
        "WSH": "WAS",
    }
    normalized = legacy_aliases.get(normalized, normalized)

    # nflplotR/nflverse logo workflows are team-abbreviation driven.
    # Use the NFL club logo endpoint keyed by cleaned team abbreviation.
    return f"https://static.www.nfl.com/t_q-best/league/api/clubs/logos/{normalized}.png"

@router.get("/search", response_model=list[PlayerSearchResult])
def search_players(
    q: str = Query(..., min_length=2), 
    pos: str = Query("ALL"), 
    league_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    # 2.2.1 CALL the service for searching
    results = player_service.search_all_players(db, q, pos, league_id)
    return [
        {
            "id": p.id,
            "name": player_service.normalize_display_name(p.name),
            "position": p.position,
            "nfl_team": p.nfl_team,
            "adp": p.adp,
            "projected_points": p.projected_points,
            "gsis_id": p.gsis_id,
            "espn_id": p.espn_id,
            "bye_week": p.bye_week,
        }
        for p in results
    ]

@router.get("/waiver-wire")
def get_free_agents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 2.3.1 CALL the service for free agent logic
    return player_service.get_league_free_agents(db, current_user.league_id)


@router.get("/top-free-agents")
def get_top_free_agents(
    league_id: int = Query(...),
    limit: int = Query(10, ge=1, le=25),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Top available players by projected rest-of-season points."""
    if current_user.league_id != league_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: cannot access another league's free agents",
        )
    return player_service.get_top_free_agents(
        db,
        league_id=current_user.league_id,
        limit=limit,
    )


@router.get("/quality-report")
def get_player_quality_report(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "requested_by_user_id": int(current_user.id),
        **player_service.get_player_quality_report(db),
    }


@router.get("/{player_id}/season-details")
def get_player_season_details(
    player_id: int,
    season: int = Query(DEFAULT_SEASON_YEAR),
    db: Session = Depends(get_db),
):
    if season < MIN_VALID_SEASON_YEAR or season > MAX_VALID_SEASON_YEAR:
        raise HTTPException(
            status_code=400,
            detail=f"season must be between {MIN_VALID_SEASON_YEAR} and {MAX_VALID_SEASON_YEAR}",
        )

    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    season_rows = (
        db.query(models.PlayerWeeklyStat)
        .filter(
            models.PlayerWeeklyStat.player_id == player_id,
            models.PlayerWeeklyStat.season == season,
        )
        .order_by(models.PlayerWeeklyStat.week.asc())
        .all()
    )

    if not season_rows:
        return {
            "player_id": player.id,
            "player_name": player_service.normalize_display_name(player.name),
            "position": player.position,
            "nfl_team": player.nfl_team,
            "espn_id": player.espn_id,
            "headshot_url": _build_headshot_url(player.espn_id),
            "team_logo_url": _build_team_logo_url(player.nfl_team),
            "season": season,
            "games_played": 0,
            "total_fantasy_points": 0.0,
            "average_fantasy_points": 0.0,
            "best_week_points": 0.0,
            "latest_week_points": 0.0,
            "weekly": [],
        }

    total_points = (
        db.query(func.coalesce(func.sum(models.PlayerWeeklyStat.fantasy_points), 0.0))
        .filter(
            models.PlayerWeeklyStat.player_id == player_id,
            models.PlayerWeeklyStat.season == season,
        )
        .scalar()
    )

    max_points = (
        db.query(func.coalesce(func.max(models.PlayerWeeklyStat.fantasy_points), 0.0))
        .filter(
            models.PlayerWeeklyStat.player_id == player_id,
            models.PlayerWeeklyStat.season == season,
        )
        .scalar()
    )

    games_played = len(season_rows)
    latest = season_rows[-1]

    return {
        "player_id": player.id,
        "player_name": player_service.normalize_display_name(player.name),
        "position": player.position,
        "nfl_team": player.nfl_team,
        "espn_id": player.espn_id,
        "headshot_url": _build_headshot_url(player.espn_id),
        "team_logo_url": _build_team_logo_url(player.nfl_team),
        "season": season,
        "games_played": games_played,
        "total_fantasy_points": float(total_points or 0.0),
        "average_fantasy_points": float((total_points or 0.0) / games_played) if games_played else 0.0,
        "best_week_points": float(max_points or 0.0),
        "latest_week_points": float(latest.fantasy_points or 0.0),
        "weekly": [
            {
                "week": row.week,
                "fantasy_points": float(row.fantasy_points or 0.0),
            }
            for row in season_rows
        ],
    }

# --- NEW: GET /players/ ---
@router.get("/", response_model=list[PlayerSearchResult])
def get_all_players(
    league_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Return all relevant fantasy players (QB, RB, WR, TE, K, DEF) from active NFL rosters."""
    deduped = player_service.get_all_relevant_players(db, league_id)
    return [
        {
            "id": p.id,
            "name": player_service.normalize_display_name(p.name),
            "position": p.position,
            "nfl_team": p.nfl_team,
            "adp": p.adp,
            "projected_points": p.projected_points,
            "gsis_id": p.gsis_id,
            "espn_id": p.espn_id,
            "bye_week": p.bye_week,
        }
        for p in deduped
    ]