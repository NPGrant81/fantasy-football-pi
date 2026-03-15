from datetime import UTC, datetime

from pydantic import BaseModel, Field


class NormalizedGame(BaseModel):
    event_id: str
    season: int | None = None
    week: int | None = None
    kickoff_utc: datetime | None = None
    status: str = "PRE"
    home_team_id: int | None = None
    away_team_id: int | None = None
    home_team_abbr: str | None = None
    away_team_abbr: str | None = None
    home_score: int = 0
    away_score: int = 0


class NormalizedPlayerStat(BaseModel):
    event_id: str
    season: int | None = None
    week: int | None = None
    player_espn_id: str
    player_name: str
    team_abbr: str | None = None
    position: str | None = None
    fantasy_points: float | None = None
    stats: dict[str, float | int | str] = Field(default_factory=dict)


class NormalizedLiveScoringPayload(BaseModel):
    source: str = "espn_site_api_v2"
    schema_version: str = "2026-03-14"
    generated_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    games: list[NormalizedGame] = Field(default_factory=list)
    player_stats: list[NormalizedPlayerStat] = Field(default_factory=list)


class ContractInspectionResult(BaseModel):
    required_paths: dict[str, bool] = Field(default_factory=dict)
    missing_paths: list[str] = Field(default_factory=list)
    event_count: int = 0
