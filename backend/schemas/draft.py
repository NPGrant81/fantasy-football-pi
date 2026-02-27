from pydantic import BaseModel, ConfigDict
from typing import Optional

# Base class (shared fields)
class DraftPickBase(BaseModel):
    player_id: int
    owner_id: int
    amount: int
    session_id: str
    year: Optional[int] = None
    # taxi status (backend will ignore these when building/storing lineups)
    is_taxi: Optional[bool] = False

# What we need to CREATE a pick (Input)
class DraftPickCreate(DraftPickBase):
    pass

# What we show to the user (Output)
class DraftPickShow(DraftPickBase):
    id: int
    year: int
    
    # migrated from Config class to ConfigDict for Pydantic v2
    model_config = ConfigDict(from_attributes=True)
