# backend/routers/players.py
from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException
from datetime import datetime
from sqlalchemy import func, exists, and_, or_
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

@router.get("/search")
def search_players(
    q: str = Query(..., min_length=2), 
    pos: str = Query("ALL"), 
    db: Session = Depends(get_db)
):
    # 2.2.1 CALL the service for searching
    results = player_service.search_all_players(db, q, pos)
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


@router.get("/{player_id}/season-details")
def get_player_season_details(
    player_id: int,
    season: int = Query(2026),
    db: Session = Depends(get_db),
):
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
@router.get("/")
def get_all_players(db: Session = Depends(get_db)):
    """Return all relevant fantasy players (QB, RB, WR, TE, K, DEF) from active NFL rosters."""
    allowed_positions = {"QB", "RB", "WR", "TE", "K", "DEF"}
    current_year = datetime.now().year

    # Players with an active PlayerSeason record in the current or prior year
    has_active_season = exists().where(
        and_(
            models.PlayerSeason.player_id == models.Player.id,
            models.PlayerSeason.is_active.is_(True),
            models.PlayerSeason.season >= current_year - 1,
        )
    )

    # Players not yet synced to PlayerSeason — include only if on an active NFL team
    has_no_season = ~exists().where(
        models.PlayerSeason.player_id == models.Player.id
    )
    inactive_teams = {"FA", "", "UAT", "TEST", "MOCK", "FAKE", "TBD", "N/A"}

    rows = (
        db.query(models.Player)
        .filter(
            models.Player.position.in_(allowed_positions),
            or_(
                has_active_season,
                and_(
                    has_no_season,
                    models.Player.nfl_team.isnot(None),
                    ~models.Player.nfl_team.in_(inactive_teams),
                ),
            ),
        )
        .order_by(models.Player.name, models.Player.id.desc())
        .all()
    )
    deduped = player_service.dedupe_players(rows)
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