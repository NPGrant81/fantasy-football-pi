from pydantic import BaseModel, ConfigDict
from typing import List, Any
# Import from sibling files using . syntax
from .user import User
from .scoring import ScoringRule

class TeamBase(BaseModel):
    name: str
    budget: int = 200

class TeamCreate(TeamBase):
    pass

class Team(TeamBase):
    id: int
    owner_id: int
    players: List[Any] = [] 

    # Pydantic v2 config
    model_config = ConfigDict(from_attributes=True)

class LeagueBase(BaseModel):
    name: str

class LeagueCreate(LeagueBase):
    pass

class League(LeagueBase):
    id: int
    users: List[User] = []
    scoring_rules: List[ScoringRule] = [] 

    model_config = ConfigDict(from_attributes=True)
