from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from ..database import get_db
from .. import models
from ..services import scoring_service
from ..services.player_service import normalize_display_name as _normalize_player_name
from ..core.security import get_current_user

router = APIRouter(
    prefix="/matchups",
    tags=["Matchups"]
)

# --- Schemas ---
class PlayerGameStats(BaseModel):
    player_id: int
    name: str
    position: str
    nfl_team: str
    projected: float
    actual: float

class TeamInfo(BaseModel):
    id: int
    name: str
    team_name: Optional[str]
    logo_url: Optional[str]
    color_primary: Optional[str]
    color_secondary: Optional[str]
    division_id: Optional[int] = None
    division_name: Optional[str] = None


class DivisionContext(BaseModel):
    is_division_matchup: bool
    home_division_id: Optional[int] = None
    away_division_id: Optional[int] = None


class RivalryContext(BaseModel):
    is_rivalry_week: bool
    rivalry_name: Optional[str] = None
    template_key: Optional[str] = None
    is_commissioner_edited: Optional[bool] = None

class MatchupSchema(BaseModel):
    id: int
    week: int
    home_team: str
    home_team_id: int
    home_team_info: TeamInfo  # <--- NEW
    home_score: float
    home_projected: float
    home_win_probability: float
    home_roster: List[PlayerGameStats] = [] # <--- NEW
    
    away_team: str
    away_team_id: int
    away_team_info: TeamInfo  # <--- NEW
    away_score: float
    away_projected: float
    away_win_probability: float
    away_roster: List[PlayerGameStats] = [] # <--- NEW
    
    is_completed: bool
    game_status: str  # <--- NEW: NOT_STARTED, IN_PROGRESS, FINAL
    label: str
    date_range: str
    division_context: DivisionContext
    rivalry_context: RivalryContext

# --- Helper: Date Calculator ---
def get_week_info(week_num: int):
    season_start = datetime(2025, 9, 4) 
    week_start = season_start + timedelta(weeks=week_num-1)
    week_end = week_start + timedelta(days=4)
    date_str = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}"
    label = "Regular Season" if week_num <= 14 else "Playoffs"
    return label, date_str

# --- Helper: Get Starters ---
def _resolve_season_year(db: Session, league_id: Optional[int]) -> int:
    if not league_id:
        return datetime.now().year

    settings = (
        db.query(models.LeagueSettings)
        .filter(models.LeagueSettings.league_id == league_id)
        .first()
    )
    if settings and settings.draft_year:
        return int(settings.draft_year)
    return datetime.now().year


def get_team_starters(
    db: Session,
    owner_id: int,
    *,
    league_id: Optional[int],
    season: int,
    week: int,
):
    """Fetch currently active starters with scoring-service projections and actuals."""
    picks_q = db.query(models.DraftPick).filter(
        models.DraftPick.owner_id == owner_id,
        models.DraftPick.current_status == 'STARTER',
    )
    if league_id is not None:
        picks_q = picks_q.filter(
            (models.DraftPick.league_id == league_id) | (models.DraftPick.league_id.is_(None))
        )
    picks = picks_q.all()

    player_ids = [pick.player_id for pick in picks if pick.player_id is not None]
    players = (
        db.query(models.Player)
        .filter(models.Player.id.in_(player_ids))
        .all()
        if player_ids
        else []
    )
    player_by_id = {player.id: player for player in players}

    roster = []
    for pick in picks:
        player = player_by_id.get(pick.player_id)
        if player:
            projected_points = 0.0
            actual_points = 0.0

            if league_id:
                calculated, _, stats_payload = scoring_service.calculate_player_week_points(
                    db,
                    league_id=league_id,
                    player_id=player.id,
                    season=season,
                    week=week,
                    position=player.position,
                    season_year=season,
                )
                projected_points = float(calculated)
                actual_points = float(stats_payload.get("fantasy_points", calculated) or 0.0)

            roster.append(PlayerGameStats(
                player_id=player.id,
                name=_normalize_player_name(player.name),
                position=player.position,
                nfl_team=player.nfl_team,
                projected=projected_points,
                actual=actual_points,
            ))
            
    # Sort by Position (QB, RB, WR, TE, K, DEF)
    pos_rank = {"QB": 1, "RB": 2, "WR": 3, "TE": 4, "K": 5, "DEF": 6}
    roster.sort(key=lambda x: pos_rank.get(x.position, 99))
    
    return roster


def calculate_win_probabilities(home_projected: float, away_projected: float) -> tuple[float, float]:
    """Return rounded home/away win percentages from projected starters totals."""
    home_value = max(float(home_projected or 0.0), 0.0)
    away_value = max(float(away_projected or 0.0), 0.0)
    total = home_value + away_value

    if total <= 0:
        return 50.0, 50.0

    home_probability = round((home_value / total) * 100, 1)
    away_probability = round(100.0 - home_probability, 1)
    return home_probability, away_probability

# --- Endpoints ---
@router.get("/week/{week_num}", response_model=List[MatchupSchema])
def get_weekly_matchups(
    week_num: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    season_year = _resolve_season_year(db, current_user.league_id)
    games = (
        db.query(models.Matchup)
        .filter(
            models.Matchup.week == week_num,
            models.Matchup.league_id == current_user.league_id,
            models.Matchup.season == season_year,
        )
        .all()
    )
    label, date_str = get_week_info(week_num)

    results = []
    for game in games:
        home = db.query(models.User).filter(models.User.id == game.home_team_id).first()
        away = db.query(models.User).filter(models.User.id == game.away_team_id).first()

        if home and away:
            season_year = _resolve_season_year(db, game.league_id)
            home_roster = get_team_starters(
                db,
                home.id,
                league_id=game.league_id,
                season=season_year,
                week=game.week,
            )
            away_roster = get_team_starters(
                db,
                away.id,
                league_id=game.league_id,
                season=season_year,
                week=game.week,
            )
            home_total_proj = sum(p.projected for p in home_roster)
            away_total_proj = sum(p.projected for p in away_roster)
            home_win_probability, away_win_probability = calculate_win_probabilities(
                home_total_proj,
                away_total_proj,
            )

            results.append(MatchupSchema(
                id=game.id,
                week=game.week,
                home_team=home.username,
                home_team_id=home.id,
                home_team_info=TeamInfo(
                    id=home.id,
                    name=home.username,
                    team_name=home.team_name,
                    logo_url=home.team_logo_url,
                    color_primary=home.team_color_primary or '#3b82f6',
                    color_secondary=home.team_color_secondary or '#1e40af',
                    division_id=home.division_id,
                    division_name=home.division_obj.name if home.division_obj else None,
                ),
                home_score=float(game.home_score or 0.0),
                home_projected=home_total_proj,
                home_win_probability=home_win_probability,
                away_team=away.username,
                away_team_id=away.id,
                away_team_info=TeamInfo(
                    id=away.id,
                    name=away.username,
                    team_name=away.team_name,
                    logo_url=away.team_logo_url,
                    color_primary=away.team_color_primary or '#3b82f6',
                    color_secondary=away.team_color_secondary or '#1e40af',
                    division_id=away.division_id,
                    division_name=away.division_obj.name if away.division_obj else None,
                ),
                away_score=float(game.away_score or 0.0),
                away_projected=away_total_proj,
                away_win_probability=away_win_probability,
                is_completed=game.is_completed,
                game_status=game.game_status or "NOT_STARTED",
                label=label,
                date_range=date_str,
                division_context=DivisionContext(
                    is_division_matchup=bool(game.is_division_matchup),
                    home_division_id=home.division_id,
                    away_division_id=away.division_id,
                ),
                rivalry_context=RivalryContext(
                    is_rivalry_week=bool(game.is_rivalry_week),
                    rivalry_name=game.rivalry_name,
                    template_key="grudge_match" if game.rivalry_name else None,
                    is_commissioner_edited=bool(game.rivalry_name),
                ),
            ))
            
    return results

@router.get("/{matchup_id}", response_model=MatchupSchema)
def get_matchup_detail(
    matchup_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    game = db.query(models.Matchup).filter(models.Matchup.id == matchup_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Matchup not found")
    if game.league_id != current_user.league_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return fetch_matchup_detail_data(matchup_id, db, game=game)


def fetch_matchup_detail_data(matchup_id: int, db: Session, *, game: Optional[models.Matchup] = None) -> MatchupSchema:
    """Internal helper: fetch matchup detail without auth checks."""
    if game is None:
        game = db.query(models.Matchup).filter(models.Matchup.id == matchup_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Matchup not found")

    home = db.query(models.User).filter(models.User.id == game.home_team_id).first()
    away = db.query(models.User).filter(models.User.id == game.away_team_id).first()
    label, date_str = get_week_info(game.week)
    season_year = _resolve_season_year(db, game.league_id)

    # Fetch Real Rosters
    home_roster = get_team_starters(
        db,
        home.id,
        league_id=game.league_id,
        season=season_year,
        week=game.week,
    )
    away_roster = get_team_starters(
        db,
        away.id,
        league_id=game.league_id,
        season=season_year,
        week=game.week,
    )

    # Recalculate Totals based on Roster (Optional polish)
    home_total_proj = sum(p.projected for p in home_roster)
    away_total_proj = sum(p.projected for p in away_roster)
    home_win_probability, away_win_probability = calculate_win_probabilities(
        home_total_proj,
        away_total_proj,
    )

    return MatchupSchema(
        id=game.id,
        week=game.week,
        home_team=home.username,
        home_team_id=home.id,
        home_team_info=TeamInfo(
            id=home.id,
            name=home.username,
            team_name=home.team_name,
            logo_url=home.team_logo_url,
            color_primary=home.team_color_primary or '#3b82f6',
            color_secondary=home.team_color_secondary or '#1e40af',
            division_id=home.division_id,
            division_name=home.division_obj.name if home.division_obj else None,
        ),
        home_score=float(game.home_score or 0.0),
        home_projected=home_total_proj, # Use sum of players
        home_win_probability=home_win_probability,
        home_roster=home_roster,        # <--- Sending Roster

        away_team=away.username,
        away_team_id=away.id,
        away_team_info=TeamInfo(
            id=away.id,
            name=away.username,
            team_name=away.team_name,
            logo_url=away.team_logo_url,
            color_primary=away.team_color_primary or '#3b82f6',
            color_secondary=away.team_color_secondary or '#1e40af',
            division_id=away.division_id,
            division_name=away.division_obj.name if away.division_obj else None,
        ),
        away_score=float(game.away_score or 0.0),
        away_projected=away_total_proj, # Use sum of players
        away_win_probability=away_win_probability,
        away_roster=away_roster,        # <--- Sending Roster

        is_completed=game.is_completed,
        game_status=game.game_status or "NOT_STARTED",
        label=label,
        date_range=date_str,
        division_context=DivisionContext(
            is_division_matchup=bool(game.is_division_matchup),
            home_division_id=home.division_id,
            away_division_id=away.division_id,
        ),
        rivalry_context=RivalryContext(
            is_rivalry_week=bool(game.is_rivalry_week),
            rivalry_name=game.rivalry_name,
            template_key="grudge_match" if game.rivalry_name else None,
            is_commissioner_edited=bool(game.rivalry_name),
        ),
    )