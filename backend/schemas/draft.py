from pydantic import BaseModel
from typing import Optional

# Base class (shared fields)
class DraftPickBase(BaseModel):
    player_id: int
    owner_id: int
    amount: int
    session_id: str

# What we need to CREATE a pick (Input)
class DraftPickCreate(DraftPickBase):
    pass

# What we show to the user (Output)
class DraftPickShow(DraftPickBase):
    id: int
    year: int
    
    class Config:
        from_attributes = True
