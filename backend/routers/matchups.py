from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from ..database import get_db
from .. import models

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

class MatchupSchema(BaseModel):
    id: int
    week: int
    home_team: str
    home_team_id: int
    home_team_info: TeamInfo  # <--- NEW
    home_score: float
    home_projected: float
    home_roster: List[PlayerGameStats] = [] # <--- NEW
    
    away_team: str
    away_team_id: int
    away_team_info: TeamInfo  # <--- NEW
    away_score: float
    away_projected: float
    away_roster: List[PlayerGameStats] = [] # <--- NEW
    
    is_completed: bool
    game_status: str  # <--- NEW: NOT_STARTED, IN_PROGRESS, FINAL
    label: str
    date_range: str

# --- Helper: Date Calculator ---
def get_week_info(week_num: int):
    season_start = datetime(2025, 9, 4) 
    week_start = season_start + timedelta(weeks=week_num-1)
    week_end = week_start + timedelta(days=4)
    date_str = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}"
    label = "Regular Season" if week_num <= 14 else "Playoffs"
    return label, date_str

# --- Helper: Get Starters ---
def get_team_starters(db: Session, owner_id: int):
    """Fetches currently active starters for a given owner."""
    picks = db.query(models.DraftPick).filter(
        models.DraftPick.owner_id == owner_id,
        models.DraftPick.current_status == 'STARTER'
    ).all()
    
    roster = []
    for pick in picks:
        player = db.query(models.Player).filter(models.Player.id == pick.player_id).first()
        if player:
            # Mock stats for now (Real logic would fetch weekly stats)
            roster.append(PlayerGameStats(
                player_id=player.id,
                name=player.name,
                position=player.position,
                nfl_team=player.nfl_team,
                projected=15.5, # Mock projection
                actual=0.0      # Mock actual
            ))
            
    # Sort by Position (QB, RB, WR, TE, K, DEF)
    pos_rank = {"QB": 1, "RB": 2, "WR": 3, "TE": 4, "K": 5, "DEF": 6}
    roster.sort(key=lambda x: pos_rank.get(x.position, 99))
    
    return roster

# --- Endpoints ---
@router.get("/week/{week_num}", response_model=List[MatchupSchema])
def get_weekly_matchups(week_num: int, db: Session = Depends(get_db)):
    games = db.query(models.Matchup).filter(models.Matchup.week == week_num).all()
    label, date_str = get_week_info(week_num)

    results = []
    for game in games:
        home = db.query(models.User).filter(models.User.id == game.home_team_id).first()
        away = db.query(models.User).filter(models.User.id == game.away_team_id).first()
        
        if home and away:
            home_roster = get_team_starters(db, home.id)
            away_roster = get_team_starters(db, away.id)
            home_total_proj = sum(p.projected for p in home_roster)
            away_total_proj = sum(p.projected for p in away_roster)

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
                    color_secondary=home.team_color_secondary or '#1e40af'
                ),
                home_score=game.home_score,
                home_projected=home_total_proj,
                away_team=away.username,
                away_team_id=away.id,
                away_team_info=TeamInfo(
                    id=away.id,
                    name=away.username,
                    team_name=away.team_name,
                    logo_url=away.team_logo_url,
                    color_primary=away.team_color_primary or '#3b82f6',
                    color_secondary=away.team_color_secondary or '#1e40af'
                ),
                away_score=game.away_score,
                away_projected=away_total_proj,
                is_completed=game.is_completed,
                game_status=game.game_status,
                label=label,
                date_range=date_str
            ))
            
    return results

@router.get("/{matchup_id}", response_model=MatchupSchema)
def get_matchup_detail(matchup_id: int, db: Session = Depends(get_db)):
    game = db.query(models.Matchup).filter(models.Matchup.id == matchup_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Matchup not found")
        
    home = db.query(models.User).filter(models.User.id == game.home_team_id).first()
    away = db.query(models.User).filter(models.User.id == game.away_team_id).first()
    label, date_str = get_week_info(game.week)

    # Fetch Real Rosters
    home_roster = get_team_starters(db, home.id)
    away_roster = get_team_starters(db, away.id)

    # Recalculate Totals based on Roster (Optional polish)
    home_total_proj = sum(p.projected for p in home_roster)
    away_total_proj = sum(p.projected for p in away_roster)

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
            color_secondary=home.team_color_secondary or '#1e40af'
        ),
        home_score=game.home_score,
        home_projected=home_total_proj, # Use sum of players
        home_roster=home_roster,        # <--- Sending Roster
        
        away_team=away.username,
        away_team_id=away.id,
        away_team_info=TeamInfo(
            id=away.id,
            name=away.username,
            team_name=away.team_name,
            logo_url=away.team_logo_url,
            color_primary=away.team_color_primary or '#3b82f6',
            color_secondary=away.team_color_secondary or '#1e40af'
        ),
        away_score=game.away_score,
        away_projected=away_total_proj, # Use sum of players
        away_roster=away_roster,        # <--- Sending Roster
        
        is_completed=game.is_completed,
        game_status=game.game_status,
        label=label,
        date_range=date_str
    )