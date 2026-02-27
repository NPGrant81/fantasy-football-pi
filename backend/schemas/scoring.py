from pydantic import BaseModel, ConfigDict
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

    model_config = ConfigDict(from_attributes=True)
