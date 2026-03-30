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


class PostDraftOwnerFocus(BaseModel):
    owner_id: int
    rank: int
    projected_points: float
    projected_points_vs_league_avg: float
    risk_score: float
    positional_gaps: list[str]
    summary: str


class PostDraftOutlookResponse(BaseModel):
    season: int
    team_rows: list[PostDraftOutlookTeamRow]
    owner_focus: PostDraftOwnerFocus | None = None
    meta: dict
