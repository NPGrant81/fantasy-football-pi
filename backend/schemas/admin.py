from pydantic import BaseModel
from typing import List, Optional

# What we need to CREATE a league
class LeagueCreate(BaseModel):
    name: str

# What the API returns to the user
class LeagueResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True # Allows reading from SQLAlchemy models