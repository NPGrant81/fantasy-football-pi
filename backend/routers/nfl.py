from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/nfl", tags=["NFL"])


from pydantic import ConfigDict

class NFLGameSchema(BaseModel):
    event_id: str
    season: int
    week: int
    home_team_id: int
    away_team_id: int
    kickoff: Optional[str] = None
    status: Optional[str] = None
    home_score: int
    away_score: int

    # Pydantic v2 style configuration (formerly ``orm_mode``)
    model_config = ConfigDict(from_attributes=True)


@router.get("/schedule/{year}/{week}", response_model=List[NFLGameSchema])
def get_weekly_schedule(year: int, week: int, db: Session = Depends(get_db)):
    """Return the NFL schedule for a particular season/week."""
    return (
        db.query(models.NFLGame)
        .filter(models.NFLGame.season == year, models.NFLGame.week == week)
        .all()
    )
