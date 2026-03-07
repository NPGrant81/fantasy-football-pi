from __future__ import annotations

import csv
import io
import re
from typing import Any

from fastapi import HTTPException

from ..schemas.scoring import ScoringRuleCreate

MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

NUMBER_PATTERN = re.compile(r"-?(?:\d*\.\d+|\d+)")

POSITION_MAP = {
    "8002": "QB",
    "8003": "RB",
    "8004": "WR",
    "8005": "TE",
    "8006": "DST",
    "8099": "K",
    "8010": "FLEX",
}

CATEGORY_KEYWORDS = {
    "passing": ["pass", "passing"],
    "rushing": ["rush", "rushing"],
    "receiving": ["receiv", "reception", "catch"],
    "kicking": ["field goal", "extra point", "kick"],
    "defense": ["def", "sack", "interception", "points allowed", "yards allowed"],
    "special_teams": ["punt return", "kickoff return"],
    "turnovers": ["fumble", "interception thrown"],
}


class ScoringImportError(ValueError):
    pass


def _first_present(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _token_to_bound(token: str, default: float) -> float:
    cleaned = token.strip().lower()
    if cleaned == "":
        return default

    month = MONTH_MAP.get(cleaned)
    if month is not None:
        return float(month)

    match = NUMBER_PATTERN.search(cleaned)
    if match:
        return float(match.group(0))

    return default


def parse_range(raw_value: str) -> tuple[float, float]:
    text = str(raw_value or "").strip()
    if not text:
        return 0.0, 9999.99

    if "-" in text:
        left, right = text.split("-", 1)
        min_value = _token_to_bound(left, 0.0)
        max_value = _token_to_bound(right, 9999.99)
    else:
        min_value = _token_to_bound(text, 0.0)
        max_value = min_value

    if min_value > max_value:
        min_value, max_value = max_value, min_value

    return float(min_value), float(max_value)


def parse_point_value(raw_value: str, explicit_type: str | None = None) -> tuple[float, str]:
    if explicit_type and str(explicit_type).strip():
        return _to_float(raw_value, 0.0), str(explicit_type).strip()

    text = str(raw_value or "").strip().lower()
    if not text:
        return 0.0, "flat_bonus"

    every_match = re.search(r"every\s+(\d+(?:\.\d+)?)", text)
    if every_match:
        denominator = float(every_match.group(1))
        if denominator > 0:
            points_match = NUMBER_PATTERN.search(text)
            numerator = float(points_match.group(0)) if points_match else 1.0
            return numerator / denominator, "per_unit"

    numeric_match = NUMBER_PATTERN.search(text)
    points = float(numeric_match.group(0)) if numeric_match else 0.0

    if "each" in text or "per" in text:
        return points, "per_unit"

    return points, "flat_bonus"


def parse_positions(raw_value: str) -> tuple[list[str], list[int]]:
    text = str(raw_value or "").strip()
    if not text:
        return ["ALL"], []

    applicable_positions: list[str] = []
    position_ids: list[int] = []

    for token in re.split(r"[;,|\s]+", text):
        cleaned = token.strip()
        if not cleaned:
            continue

        if cleaned.isdigit():
            position_ids.append(int(cleaned))
            mapped = POSITION_MAP.get(cleaned)
            if mapped:
                applicable_positions.append(mapped)
            continue

        mapped = POSITION_MAP.get(cleaned)
        if mapped:
            applicable_positions.append(mapped)
        else:
            applicable_positions.append(cleaned.upper())

    normalized_positions = sorted(set(applicable_positions)) if applicable_positions else ["ALL"]
    normalized_ids = sorted(set(position_ids))
    return normalized_positions, normalized_ids


def infer_category(event_name: str) -> str:
    normalized = event_name.strip().lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return "custom"


def sanitize_external_row(
    row: dict[str, Any],
    *,
    source_platform: str = "imported",
    season_year: int | None = None,
) -> dict[str, Any]:
    event_name = _first_present(row, "event_name", "Event", "event", "Rule", "rule")
    if not event_name:
        raise ScoringImportError("Missing event name column (event_name/Event)")

    category = _first_present(row, "category", "Category") or infer_category(event_name)

    range_min_raw = row.get("range_min")
    range_max_raw = row.get("range_max")
    if range_min_raw is not None or range_max_raw is not None:
        range_min = _to_float(range_min_raw, 0.0)
        range_max = _to_float(range_max_raw, 9999.99)
        if range_min > range_max:
            range_min, range_max = range_max, range_min
    else:
        range_text = _first_present(row, "Range_Yds", "Range", "range")
        range_min, range_max = parse_range(range_text)

    explicit_type = _first_present(row, "calculation_type", "CalculationType") or None
    point_raw = _first_present(row, "point_value", "Point_Value", "points", "Points")
    point_value, calculation_type = parse_point_value(point_raw, explicit_type)

    positions_raw = _first_present(
        row,
        "applicable_positions",
        "position_ids",
        "PostionID",
        "PositionID",
        "positions",
    )
    applicable_positions, position_ids = parse_positions(positions_raw)

    if "position_ids" in row and str(row.get("position_ids") or "").strip():
        _, position_ids = parse_positions(str(row.get("position_ids")))

    if "applicable_positions" in row and str(row.get("applicable_positions") or "").strip():
        explicit_positions, _ = parse_positions(str(row.get("applicable_positions")))
        applicable_positions = explicit_positions

    parsed_season = season_year
    if parsed_season is None and row.get("season_year") not in (None, ""):
        parsed_season = int(float(str(row.get("season_year"))))

    return {
        "category": category,
        "event_name": event_name,
        "description": _first_present(row, "description", "Description") or None,
        "range_min": range_min,
        "range_max": range_max,
        "point_value": point_value,
        "calculation_type": calculation_type,
        "applicable_positions": applicable_positions,
        "position_ids": position_ids,
        "season_year": parsed_season,
        "source": source_platform,
        "is_active": True,
    }


def parse_csv_rows_to_rules(
    csv_content: str,
    *,
    source_platform: str = "imported",
    season_year: int | None = None,
) -> list[ScoringRuleCreate]:
    reader = csv.DictReader(io.StringIO(csv_content))
    if not reader.fieldnames:
        raise ScoringImportError("CSV content is missing headers")

    parsed: list[ScoringRuleCreate] = []
    errors: list[str] = []

    for line_number, row in enumerate(reader, start=2):
        try:
            sanitized = sanitize_external_row(
                row,
                source_platform=source_platform,
                season_year=season_year,
            )
            parsed.append(ScoringRuleCreate(**sanitized))
        except (ValueError, ScoringImportError) as exc:
            errors.append(f"line {line_number}: {exc}")

    if errors:
        raise ScoringImportError("; ".join(errors))

    if not parsed:
        raise ScoringImportError("CSV did not contain any valid scoring rules")

    return parsed


def parse_csv_rows_to_preview(
    csv_content: str,
    *,
    source_platform: str = "imported",
    season_year: int | None = None,
) -> list[dict[str, Any]]:
    rules = parse_csv_rows_to_rules(
        csv_content,
        source_platform=source_platform,
        season_year=season_year,
    )
    return [rule.model_dump() for rule in rules]


def raise_http_400_for_import_error(exc: Exception) -> None:
    if isinstance(exc, (ScoringImportError, ValueError)):
        raise HTTPException(status_code=400, detail=str(exc))
    raise
