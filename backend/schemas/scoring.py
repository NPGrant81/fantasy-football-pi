from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

class ScoringRuleBase(BaseModel):
    category: str
    event_name: str
    description: str | None = None
    range_min: float = 0
    range_max: float = 9999.99
    point_value: float
    calculation_type: str = "flat_bonus"
    applicable_positions: list[str] = Field(default_factory=list)
    position_ids: list[int] = Field(default_factory=list)
    season_year: int | None = None
    source: str = "custom"
    is_active: bool = True

    @model_validator(mode="before")
    @classmethod
    def _map_legacy_keys(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        # Backward compatibility for older payloads used in this repository.
        if "min_val" in values and "range_min" not in values:
            values["range_min"] = values["min_val"]
        if "max_val" in values and "range_max" not in values:
            values["range_max"] = values["max_val"]
        if "points" in values and "point_value" not in values:
            values["point_value"] = values["points"]
        if "position_target" in values and "applicable_positions" not in values:
            target = values.get("position_target")
            values["applicable_positions"] = [target] if target else []
        if "event_name" not in values and "category" in values:
            values["event_name"] = str(values["category"])

        return values

class ScoringRuleCreate(ScoringRuleBase):
    pass

class ScoringRule(ScoringRuleBase):
    id: int
    league_id: int
    template_id: int | None = None
    created_by_user_id: int | None = None
    updated_by_user_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class ScoringTemplateBase(BaseModel):
    name: str
    description: str | None = None
    season_year: int | None = None
    source_platform: str = "custom"
    is_system_template: bool = False
    is_active: bool = True


class ScoringTemplateCreate(ScoringTemplateBase):
    pass


class ScoringTemplate(ScoringTemplateBase):
    id: int
    league_id: int

    model_config = ConfigDict(from_attributes=True)


class ScoringRuleProposalBase(BaseModel):
    title: str
    description: str | None = None
    proposed_change: dict[str, Any]
    season_year: int | None = None
    status: str = "open"


class ScoringRuleProposalCreate(ScoringRuleProposalBase):
    pass


class ScoringRuleProposal(ScoringRuleProposalBase):
    id: int
    league_id: int

    model_config = ConfigDict(from_attributes=True)
