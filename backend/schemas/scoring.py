from pydantic import BaseModel
from typing import Optional

class ScoringRuleBase(BaseModel):
    category: str
    min_val: float
    max_val: float
    points: float
    position_target: Optional[str] = None

class ScoringRuleCreate(ScoringRuleBase):
    pass

class ScoringRule(ScoringRuleBase):
    id: int
    league_id: int

    class Config:
        from_attributes = True
