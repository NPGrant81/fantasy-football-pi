from typing import Literal

from pydantic import BaseModel


class PostDraftOutlookTeamRow(BaseModel):
    owner_id: int
    owner_name: str
    team_name: str
    rank: int
    roster_size: int
    projected_points: float
    projected_points_vs_league_avg: float
    risk_score: float
    positional_balance_score: float
    strength_score: float
    confidence_score: float
    confidence_label: Literal["low", "moderate", "high"]


class PostDraftOwnerFocus(BaseModel):
    owner_id: int
    rank: int
    projected_points: float
    projected_points_vs_league_avg: float
    risk_score: float
    confidence_score: float
    confidence_label: Literal["low", "moderate", "high"]
    positional_gaps: list[str]
    summary: str


class PostDraftOutlookDataQuality(BaseModel):
    total_draft_rows: int
    included_rows: int
    skipped_rows: int
    duplicate_rows_skipped: int
    invalid_projection_rows: int
    unknown_position_rows: int
    projection_coverage: float


class PostDraftOutlookConfidenceContext(BaseModel):
    method: str
    model_signal_available: bool
    simulation_signal_available: bool
    baseline_only: bool


class PostDraftOutlookMeta(BaseModel):
    metric: str
    league_id: int
    season: int
    scoring_profile: dict
    computed_at: str
    degraded_mode: bool
    degradation_reasons: list[str]
    data_quality: PostDraftOutlookDataQuality
    confidence_context: PostDraftOutlookConfidenceContext


class PostDraftOutlookResponse(BaseModel):
    season: int
    team_rows: list[PostDraftOutlookTeamRow]
    owner_focus: PostDraftOwnerFocus | None = None
    meta: PostDraftOutlookMeta
