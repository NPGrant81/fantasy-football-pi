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


class HistoricalRankingResponse(BaseModel):
    player_id: int
    player_name: str
    position: Optional[str] = None
    season: int
    rank: int
    predicted_auction_value: float
    value_over_replacement: float
    consensus_tier: Optional[str] = None
    final_score: float = 0.0
    league_position_weight: float = 1.0
    owner_position_affinity: float = 1.0
    owner_player_affinity: float = 1.0
    keeper_scarcity_boost: float = 1.0
    availability_factor: float = 1.0
    scoring_consistency_factor: float = 1.0
    late_start_consistency_factor: float = 1.0
    injury_split_factor: float = 1.0
    team_change_factor: float = 1.0
    price_min: Optional[float] = None
    price_avg: Optional[float] = None
    price_max: Optional[float] = None
    source_count: Optional[int] = None
    sources: Optional[list[str]] = None
    adp: Optional[float] = None
