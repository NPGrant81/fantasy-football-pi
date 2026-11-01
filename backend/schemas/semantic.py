from typing import Literal

from pydantic import BaseModel, Field


SourceStatus = Literal["known", "mixed", "unknown"]
PointBasis = Literal["source_reported", "league_calculated", "unknown"]
ScoringDefinitionStatus = Literal["known", "unversioned", "unknown"]
ValueStatus = Literal["known", "partial", "unknown"]
FreshnessStatus = Literal[
    "fresh",
    "stale",
    "unknown",
    "unavailable",
    "not_applicable",
]


class SemanticScope(BaseModel):
    league_id: int | None = None
    player_id: int | None = None
    season: int | None = None
    week: int | None = None


class SemanticPointContext(BaseModel):
    source_status: SourceStatus = "unknown"
    sources: list[str] = Field(default_factory=list)
    unknown_source_count: int = 0
    value_basis: PointBasis = "unknown"
    scoring_definition: ScoringDefinitionStatus = "unknown"
    selection_policy: str
    observed_at: str | None = None
    freshness: FreshnessStatus = "unknown"
    value_status: ValueStatus = "unknown"
    value_count: int = 0
    unknown_value_count: int = 0


class SemanticMembershipContext(BaseModel):
    basis: Literal["not_applicable", "current_draft_pick_status", "unknown"]
    league_scoped: bool
    season_scoped: bool
    week_scoped: bool
    historical_status: Literal["not_applicable", "current_only", "unknown"]
    allows_unscoped_legacy_picks: bool = False


class SemanticContext(BaseModel):
    metric: str
    scope: SemanticScope
    calculation_scope: SemanticScope | None = None
    aggregation: str | None = None
    points: SemanticPointContext | None = None
    projected: SemanticPointContext | None = None
    actual: SemanticPointContext | None = None
    stored_scores: SemanticPointContext | None = None
    home_projected: SemanticPointContext | None = None
    away_projected: SemanticPointContext | None = None
    membership: SemanticMembershipContext
