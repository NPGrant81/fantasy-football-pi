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


class DraftHistoryEvent(BaseModel):
    id: int | str
    owner_id: int
    player_id: int
    amount: int | str
    timestamp: str | None = None
    position: str | None = None
    player_name: str | None = None
    is_keeper: bool
    source: str | None = None
    source_event_id: str | None = None
    event_grain: str | None = None
    chronology_established: bool | None = None
    snapshot_nfl_team: str | None = None
    snapshot_team_labels: list[str] | None = None
    team_basis: str | None = None
    source_timestamp: str | None = None
    owner_label: str | None = None


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
    confidence_score: Optional[float] = None
    sentiment_score_7d: float = 0.0
    sentiment_label: Optional[str] = None
    mention_count_7d: int = 0
    # Injury / availability
    injury_status: Optional[str] = None
    injury_notes: Optional[str] = None
    projected_return_date: Optional[str] = None
    projected_return_week: Optional[int] = None
