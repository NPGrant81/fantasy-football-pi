# backend/routers/players.py
from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
import models
from core.security import get_current_user, check_is_commissioner 
from services import player_service # 2.1.1 IMPORT the service logic

router = APIRouter(
    prefix="/players",
    tags=["Players"]
)

@router.get("/search")
def search_players(
    q: str = Query(..., min_length=2), 
    pos: str = Query("ALL"), 
    db: Session = Depends(get_db)
):
    # 2.2.1 CALL the service for searching
    return player_service.search_all_players(db, q, pos)

@router.get("/waiver-wire")
def get_free_agents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 2.3.1 CALL the service for free agent logic
    return player_service.get_league_free_agents(db, current_user.league_id)


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
            "player_name": player.name,
            "position": player.position,
            "nfl_team": player.nfl_team,
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
        "player_name": player.name,
        "position": player.position,
        "nfl_team": player.nfl_team,
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
    return db.query(models.Player).filter(
        models.Player.position.in_(allowed_positions)
    ).order_by(models.Player.position, models.Player.name).all()