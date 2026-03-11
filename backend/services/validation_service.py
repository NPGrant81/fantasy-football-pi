from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError


@dataclass
class ValidationReport:
    valid: bool
    engine: str
    errors: dict[str, Any] = field(default_factory=dict)
    normalized: dict[str, Any] | None = None


class WaiverClaimBoundaryModel(BaseModel):
    player_id: int = Field(gt=0)
    bid_amount: int = Field(ge=0)
    drop_player_id: int | None = Field(default=None, gt=0)
    team_id: int | None = Field(default=None, gt=0)


class DraftPickBoundaryModel(BaseModel):
    owner_id: int = Field(gt=0)
    player_id: int = Field(gt=0)
    amount: int = Field(ge=1)
    session_id: str = Field(min_length=1, max_length=128)
    year: int | None = Field(default=None, ge=2000, le=2100)


class TradeProposalBoundaryModel(BaseModel):
    to_user_id: int = Field(gt=0)
    offered_player_id: int = Field(gt=0)
    requested_player_id: int = Field(gt=0)
    offered_dollars: float | None = Field(default=0, ge=0)
    requested_dollars: float | None = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=500)


class LeagueSettingsBoundaryModel(BaseModel):
    roster_size: int = Field(ge=1, le=40)
    salary_cap: int = Field(ge=0, le=10000)
    starting_slots: dict[str, int]
    waiver_deadline: str | None = Field(default=None, max_length=128)
    starting_waiver_budget: int | None = Field(default=None, ge=0, le=10000)
    waiver_system: str | None = Field(default=None, max_length=32)
    waiver_tiebreaker: str | None = Field(default=None, max_length=32)
    trade_deadline: str | None = Field(default=None, max_length=128)
    draft_year: int | None = Field(default=None, ge=2000, le=2100)
    scoring_rules: list[dict[str, Any]]


class PlayoffSettingsBoundaryModel(BaseModel):
    playoff_qualifiers: int | None = Field(default=None, ge=2, le=16)
    playoff_reseed: bool | None = None
    playoff_consolation: bool | None = None
    playoff_tiebreakers: list[str] | None = None


class KeeperSettingsBoundaryModel(BaseModel):
    max_keepers: int | None = Field(default=None, ge=0, le=20)
    max_years_per_player: int | None = Field(default=None, ge=1, le=10)
    deadline_date: datetime | None = None
    waiver_policy: bool | None = None
    trade_deadline: datetime | None = None
    drafted_only: bool | None = None
    cost_type: str | None = Field(default=None, max_length=32)
    cost_inflation: int | None = Field(default=None, ge=0, le=100)


CERBERUS_WAIVER_SCHEMA = {
    "player_id": {"type": "integer", "min": 1, "required": True},
    "bid_amount": {"type": "integer", "min": 0, "required": True},
    "drop_player_id": {"type": "integer", "min": 1, "nullable": True, "required": False},
    "team_id": {"type": "integer", "min": 1, "nullable": True, "required": False},
}


def validate_waiver_claim_boundary(payload: dict[str, Any]) -> ValidationReport:
    try:
        model = WaiverClaimBoundaryModel(**payload)
        return ValidationReport(
            valid=True,
            engine="pydantic",
            normalized=model.model_dump(),
        )
    except ValidationError as exc:
        return ValidationReport(
            valid=False,
            engine="pydantic",
            errors={"detail": exc.errors()},
        )


def validate_draft_pick_boundary(payload: dict[str, Any]) -> ValidationReport:
    try:
        model = DraftPickBoundaryModel(**payload)
        return ValidationReport(
            valid=True,
            engine="pydantic",
            normalized=model.model_dump(),
        )
    except ValidationError as exc:
        return ValidationReport(
            valid=False,
            engine="pydantic",
            errors={"detail": exc.errors()},
        )


def _manual_dynamic_draft_validation(payload: dict[str, Any]) -> ValidationReport:
    errors: dict[str, list[str]] = {}
    session_id = str(payload.get("session_id") or "")

    if session_id != session_id.strip():
        errors.setdefault("session_id", []).append("cannot start or end with whitespace")
    if " " in session_id:
        errors.setdefault("session_id", []).append("cannot contain spaces")

    return ValidationReport(
        valid=not errors,
        engine="manual",
        errors=errors,
        normalized=payload if not errors else None,
    )


def validate_draft_pick_dynamic_rules(payload: dict[str, Any]) -> ValidationReport:
    try:
        from cerberus import Validator  # type: ignore
    except Exception:
        return _manual_dynamic_draft_validation(payload)

    schema = {
        "owner_id": {"type": "integer", "min": 1, "required": True},
        "player_id": {"type": "integer", "min": 1, "required": True},
        "amount": {"type": "integer", "min": 1, "required": True},
        "session_id": {
            "type": "string",
            "minlength": 1,
            "maxlength": 128,
            "required": True,
            "regex": r"^[^\s]+$",
        },
        "year": {"type": "integer", "nullable": True, "required": False},
    }
    validator = Validator(schema)
    ok = validator.validate(payload)

    if ok:
        return ValidationReport(valid=True, engine="cerberus", normalized=validator.document)

    return ValidationReport(valid=False, engine="cerberus", errors=dict(validator.errors))


def validate_trade_proposal_boundary(payload: dict[str, Any]) -> ValidationReport:
    try:
        model = TradeProposalBoundaryModel(**payload)
        return ValidationReport(
            valid=True,
            engine="pydantic",
            normalized=model.model_dump(),
        )
    except ValidationError as exc:
        return ValidationReport(
            valid=False,
            engine="pydantic",
            errors={"detail": exc.errors()},
        )


def validate_league_settings_boundary(payload: dict[str, Any]) -> ValidationReport:
    try:
        model = LeagueSettingsBoundaryModel(**payload)
        return ValidationReport(
            valid=True,
            engine="pydantic",
            normalized=model.model_dump(),
        )
    except ValidationError as exc:
        return ValidationReport(
            valid=False,
            engine="pydantic",
            errors={"detail": exc.errors()},
        )


def _manual_dynamic_league_settings_validation(payload: dict[str, Any]) -> ValidationReport:
    errors: dict[str, list[str]] = {}
    starting_slots = payload.get("starting_slots")
    roster_size = payload.get("roster_size")
    scoring_rules = payload.get("scoring_rules")

    if not isinstance(starting_slots, dict) or not starting_slots:
        errors.setdefault("starting_slots", []).append("must include at least one slot")
    else:
        total_slots = 0
        counted_starter_slots = 0
        for key, value in starting_slots.items():
            if not isinstance(key, str) or not key.strip():
                errors.setdefault("starting_slots", []).append("contains an invalid slot key")
                continue
            if not isinstance(value, int) or value < 0:
                errors.setdefault(f"starting_slots.{key}", []).append("must be a non-negative integer")
                continue

            # Only count concrete starter slots (QB/RB/WR/...) toward the lineup sum.
            # Metadata keys like MAX_QB, ACTIVE_ROSTER_SIZE, toggles, etc. should not
            # be included in this check.
            normalized_key = key.strip().upper()
            if "_" not in normalized_key:
                total_slots += value
                counted_starter_slots += 1

        if counted_starter_slots > 0:
            active_roster_size = starting_slots.get("ACTIVE_ROSTER_SIZE")
            # Lineup slot totals are constrained by active starters, not total roster size.
            # Fallback to roster_size only when ACTIVE_ROSTER_SIZE is not provided.
            limit = active_roster_size if isinstance(active_roster_size, int) else roster_size
            if isinstance(limit, int) and total_slots > limit:
                errors.setdefault("starting_slots", []).append(
                    "sum of starting slots cannot exceed ACTIVE_ROSTER_SIZE"
                )

    if not isinstance(scoring_rules, list) or len(scoring_rules) == 0:
        errors.setdefault("scoring_rules", []).append("must include at least one scoring rule")

    waiver_system = payload.get("waiver_system")
    if isinstance(waiver_system, str) and waiver_system.strip():
        normalized_system = waiver_system.strip().upper()
        allowed_systems = {"FAAB", "PRIORITY", "BOTH"}
        if normalized_system not in allowed_systems:
            errors.setdefault("waiver_system", []).append(
                "must be one of: FAAB, PRIORITY, BOTH"
            )

    waiver_tiebreaker = payload.get("waiver_tiebreaker")
    if isinstance(waiver_tiebreaker, str) and waiver_tiebreaker.strip():
        normalized_tiebreaker = waiver_tiebreaker.strip().lower()
        allowed_tiebreakers = {"standings", "priority", "timestamp"}
        if normalized_tiebreaker not in allowed_tiebreakers:
            errors.setdefault("waiver_tiebreaker", []).append(
                "must be one of: standings, priority, timestamp"
            )

    return ValidationReport(
        valid=not errors,
        engine="manual",
        errors=errors,
        normalized=payload if not errors else None,
    )


def validate_league_settings_dynamic_rules(payload: dict[str, Any]) -> ValidationReport:
    try:
        from cerberus import Validator  # type: ignore
    except Exception:
        return _manual_dynamic_league_settings_validation(payload)

    schema = {
        "roster_size": {"type": "integer", "min": 1, "max": 40, "required": True},
        "salary_cap": {"type": "integer", "min": 0, "max": 10000, "required": True},
        "starting_slots": {"type": "dict", "required": True},
        "waiver_deadline": {"type": "string", "nullable": True, "required": False},
        "starting_waiver_budget": {
            "type": "integer",
            "min": 0,
            "max": 10000,
            "nullable": True,
            "required": False,
        },
        "waiver_system": {"type": "string", "nullable": True, "required": False},
        "waiver_tiebreaker": {"type": "string", "nullable": True, "required": False},
        "trade_deadline": {"type": "string", "nullable": True, "required": False},
        "draft_year": {
            "type": "integer",
            "nullable": True,
            "min": 2000,
            "max": 2100,
            "required": False,
        },
        "scoring_rules": {
            "type": "list",
            "required": True,
            "minlength": 1,
        },
    }

    validator = Validator(schema)
    base_ok = validator.validate(payload)
    custom_report = _manual_dynamic_league_settings_validation(payload)

    if base_ok and custom_report.valid:
        return ValidationReport(valid=True, engine="cerberus", normalized=validator.document)

    merged_errors: dict[str, Any] = {}
    if validator.errors:
        merged_errors.update(validator.errors)
    for key, value in custom_report.errors.items():
        merged_errors.setdefault(key, [])
        merged_errors[key].extend(value)

    return ValidationReport(valid=False, engine="cerberus", errors=merged_errors)


def validate_playoff_settings_boundary(payload: dict[str, Any]) -> ValidationReport:
    try:
        model = PlayoffSettingsBoundaryModel(**payload)
        return ValidationReport(
            valid=True,
            engine="pydantic",
            normalized=model.model_dump(),
        )
    except ValidationError as exc:
        return ValidationReport(
            valid=False,
            engine="pydantic",
            errors={"detail": exc.errors()},
        )


def _manual_dynamic_playoff_settings_validation(payload: dict[str, Any]) -> ValidationReport:
    errors: dict[str, list[str]] = {}

    playoff_qualifiers = payload.get("playoff_qualifiers")
    if playoff_qualifiers is not None and isinstance(playoff_qualifiers, int):
        if playoff_qualifiers % 2 != 0:
            errors.setdefault("playoff_qualifiers", []).append("must be an even number")

    playoff_tiebreakers = payload.get("playoff_tiebreakers")
    if playoff_tiebreakers is not None:
        if not isinstance(playoff_tiebreakers, list):
            errors.setdefault("playoff_tiebreakers", []).append("must be a list")
        elif len(playoff_tiebreakers) == 0:
            errors.setdefault("playoff_tiebreakers", []).append("must include at least one tiebreaker")
        else:
            allowed_tiebreakers = {
                "overall_record",
                "head_to_head",
                "points_for",
                "points_against",
                "random_draw",
            }
            normalized = []
            for value in playoff_tiebreakers:
                if not isinstance(value, str):
                    errors.setdefault("playoff_tiebreakers", []).append("values must be strings")
                    continue
                token = value.strip().lower()
                normalized.append(token)
                if token not in allowed_tiebreakers:
                    errors.setdefault("playoff_tiebreakers", []).append(
                        "contains unsupported value"
                    )
            if len(set(normalized)) != len(normalized):
                errors.setdefault("playoff_tiebreakers", []).append("must not contain duplicates")

    return ValidationReport(
        valid=not errors,
        engine="manual",
        errors=errors,
        normalized=payload if not errors else None,
    )


def validate_playoff_settings_dynamic_rules(payload: dict[str, Any]) -> ValidationReport:
    try:
        from cerberus import Validator  # type: ignore
    except Exception:
        return _manual_dynamic_playoff_settings_validation(payload)

    schema = {
        "playoff_qualifiers": {
            "type": "integer",
            "nullable": True,
            "min": 2,
            "max": 16,
            "required": False,
        },
        "playoff_reseed": {"type": "boolean", "nullable": True, "required": False},
        "playoff_consolation": {"type": "boolean", "nullable": True, "required": False},
        "playoff_tiebreakers": {"type": "list", "nullable": True, "required": False},
    }
    validator = Validator(schema)
    base_ok = validator.validate(payload)
    custom_report = _manual_dynamic_playoff_settings_validation(payload)

    if base_ok and custom_report.valid:
        return ValidationReport(valid=True, engine="cerberus", normalized=validator.document)

    merged_errors: dict[str, Any] = {}
    if validator.errors:
        merged_errors.update(validator.errors)
    for key, value in custom_report.errors.items():
        merged_errors.setdefault(key, [])
        merged_errors[key].extend(value)

    return ValidationReport(valid=False, engine="cerberus", errors=merged_errors)


def validate_keeper_settings_boundary(payload: dict[str, Any]) -> ValidationReport:
    try:
        model = KeeperSettingsBoundaryModel(**payload)
        return ValidationReport(
            valid=True,
            engine="pydantic",
            normalized=model.model_dump(),
        )
    except ValidationError as exc:
        return ValidationReport(
            valid=False,
            engine="pydantic",
            errors={"detail": exc.errors()},
        )


def _manual_dynamic_keeper_settings_validation(payload: dict[str, Any]) -> ValidationReport:
    errors: dict[str, list[str]] = {}

    cost_type = payload.get("cost_type")
    if isinstance(cost_type, str) and cost_type.strip():
        allowed_cost_types = {"round", "value", "custom"}
        if cost_type.strip().lower() not in allowed_cost_types:
            errors.setdefault("cost_type", []).append("must be one of: round, value, custom")

    deadline_date = payload.get("deadline_date")
    trade_deadline = payload.get("trade_deadline")
    if isinstance(deadline_date, datetime) and isinstance(trade_deadline, datetime):
        if deadline_date > trade_deadline:
            errors.setdefault("deadline_date", []).append("must be on or before trade_deadline")

    return ValidationReport(
        valid=not errors,
        engine="manual",
        errors=errors,
        normalized=payload if not errors else None,
    )


def validate_keeper_settings_dynamic_rules(payload: dict[str, Any]) -> ValidationReport:
    try:
        from cerberus import Validator  # type: ignore
    except Exception:
        return _manual_dynamic_keeper_settings_validation(payload)

    schema = {
        "max_keepers": {
            "type": "integer",
            "nullable": True,
            "min": 0,
            "max": 20,
            "required": False,
        },
        "max_years_per_player": {
            "type": "integer",
            "nullable": True,
            "min": 1,
            "max": 10,
            "required": False,
        },
        "deadline_date": {"type": "datetime", "nullable": True, "required": False},
        "waiver_policy": {"type": "boolean", "nullable": True, "required": False},
        "trade_deadline": {"type": "datetime", "nullable": True, "required": False},
        "drafted_only": {"type": "boolean", "nullable": True, "required": False},
        "cost_type": {"type": "string", "nullable": True, "required": False},
        "cost_inflation": {
            "type": "integer",
            "nullable": True,
            "min": 0,
            "max": 100,
            "required": False,
        },
    }
    validator = Validator(schema)
    base_ok = validator.validate(payload)
    custom_report = _manual_dynamic_keeper_settings_validation(payload)

    if base_ok and custom_report.valid:
        return ValidationReport(valid=True, engine="cerberus", normalized=validator.document)

    merged_errors: dict[str, Any] = {}
    if validator.errors:
        merged_errors.update(validator.errors)
    for key, value in custom_report.errors.items():
        merged_errors.setdefault(key, [])
        merged_errors[key].extend(value)

    return ValidationReport(valid=False, engine="cerberus", errors=merged_errors)


def _manual_dynamic_trade_validation(payload: dict[str, Any]) -> ValidationReport:
    errors: dict[str, list[str]] = {}

    if payload.get("to_user_id") == payload.get("current_user_id"):
        errors.setdefault("to_user_id", []).append("cannot trade with yourself")
    if payload.get("offered_player_id") == payload.get("requested_player_id"):
        errors.setdefault("requested_player_id", []).append("must differ from offered_player_id")

    return ValidationReport(
        valid=not errors,
        engine="manual",
        errors=errors,
        normalized=payload if not errors else None,
    )


def validate_trade_proposal_dynamic_rules(payload: dict[str, Any]) -> ValidationReport:
    try:
        from cerberus import Validator  # type: ignore
    except Exception:
        return _manual_dynamic_trade_validation(payload)

    schema = {
        "current_user_id": {"type": "integer", "min": 1, "required": True},
        "to_user_id": {"type": "integer", "min": 1, "required": True},
        "offered_player_id": {"type": "integer", "min": 1, "required": True},
        "requested_player_id": {"type": "integer", "min": 1, "required": True},
        "offered_dollars": {"type": "float", "min": 0, "required": True},
        "requested_dollars": {"type": "float", "min": 0, "required": True},
    }
    validator = Validator(schema)
    ok = validator.validate(payload)

    custom_errors: dict[str, list[str]] = {}
    if payload.get("to_user_id") == payload.get("current_user_id"):
        custom_errors.setdefault("to_user_id", []).append("cannot trade with yourself")
    if payload.get("offered_player_id") == payload.get("requested_player_id"):
        custom_errors.setdefault("requested_player_id", []).append("must differ from offered_player_id")

    if ok and not custom_errors:
        return ValidationReport(valid=True, engine="cerberus", normalized=validator.document)

    merged_errors: dict[str, Any] = {}
    if validator.errors:
        merged_errors.update(validator.errors)
    for key, value in custom_errors.items():
        merged_errors.setdefault(key, [])
        merged_errors[key].extend(value)

    return ValidationReport(valid=False, engine="cerberus", errors=merged_errors)


def _manual_dynamic_waiver_validation(payload: dict[str, Any]) -> ValidationReport:
    errors: dict[str, list[str]] = {}

    player_id = payload.get("player_id")
    bid_amount = payload.get("bid_amount")
    drop_player_id = payload.get("drop_player_id")

    if isinstance(player_id, int) and isinstance(drop_player_id, int) and player_id == drop_player_id:
        errors.setdefault("drop_player_id", []).append("cannot equal player_id")

    if isinstance(bid_amount, int) and bid_amount > 1000:
        errors.setdefault("bid_amount", []).append("must be <= 1000")

    return ValidationReport(
        valid=not errors,
        engine="manual",
        errors=errors,
        normalized=payload if not errors else None,
    )


def validate_waiver_claim_dynamic_rules(payload: dict[str, Any]) -> ValidationReport:
    try:
        from cerberus import Validator  # type: ignore
    except Exception:
        return _manual_dynamic_waiver_validation(payload)

    validator = Validator(CERBERUS_WAIVER_SCHEMA)
    cerberus_ok = validator.validate(payload)

    custom_errors: dict[str, list[str]] = {}
    if payload.get("player_id") == payload.get("drop_player_id") and payload.get("drop_player_id") is not None:
        custom_errors.setdefault("drop_player_id", []).append("cannot equal player_id")
    if isinstance(payload.get("bid_amount"), int) and payload["bid_amount"] > 1000:
        custom_errors.setdefault("bid_amount", []).append("must be <= 1000")

    if cerberus_ok and not custom_errors:
        return ValidationReport(
            valid=True,
            engine="cerberus",
            normalized=validator.document,
        )

    merged_errors: dict[str, Any] = {}
    if validator.errors:
        merged_errors.update(validator.errors)
    if custom_errors:
        for key, value in custom_errors.items():
            merged_errors.setdefault(key, [])
            merged_errors[key].extend(value)

    return ValidationReport(
        valid=False,
        engine="cerberus",
        errors=merged_errors,
    )


def serialize_ledger_entries(entries: list[dict[str, Any] | Any]) -> list[dict[str, Any]]:
    try:
        from marshmallow import Schema, fields  # type: ignore
    except Exception:
        serialized: list[dict[str, Any]] = []
        for item in entries:
            if isinstance(item, dict):
                serialized.append(dict(item))
            else:
                serialized.append({
                    "id": getattr(item, "id", None),
                    "currency_type": getattr(item, "currency_type", None),
                    "amount": getattr(item, "amount", None),
                    "transaction_type": getattr(item, "transaction_type", None),
                })
        return serialized

    class LedgerEntrySchema(Schema):
        id = fields.Integer(required=False, allow_none=True)
        currency_type = fields.String(required=False, allow_none=True)
        amount = fields.Integer(required=False, allow_none=True)
        transaction_type = fields.String(required=False, allow_none=True)

    schema = LedgerEntrySchema(many=True)
    materialized = []
    for item in entries:
        if isinstance(item, dict):
            materialized.append(item)
        else:
            materialized.append({
                "id": getattr(item, "id", None),
                "currency_type": getattr(item, "currency_type", None),
                "amount": getattr(item, "amount", None),
                "transaction_type": getattr(item, "transaction_type", None),
            })

    return schema.dump(materialized)
