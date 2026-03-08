"""CSV importer and migration helper for scoring rules."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import Base, SessionLocal, engine
from backend.services.scoring_import_service import (
    ScoringImportError,
    parse_csv_rows_to_rules,
    sanitize_external_row,
)


def sanitize_row(row: dict) -> dict:
    """Backwards-compatible sanitizer used by existing tests."""
    return sanitize_external_row(row)


def insert_rules(league_id: int, records: list[dict]) -> None:
    db = SessionLocal()
    Base.metadata.create_all(bind=engine)

    import backend.models as models

    try:
        league = db.query(models.League).filter(models.League.id == league_id).first()
        if league is None:
            league = models.League(id=league_id, name=f"Imported League {league_id}")
            db.add(league)
            db.flush()

        new_rules: list[models.ScoringRule] = []
        for record in records:
            new_rules.append(
                models.ScoringRule(
                    league_id=league_id,
                    category=record.get("category", "custom"),
                    event_name=record.get("event_name", ""),
                    description=record.get("description"),
                    range_min=record.get("range_min", 0),
                    range_max=record.get("range_max", 9999.99),
                    point_value=record.get("point_value", 0),
                    calculation_type=record.get("calculation_type", "flat_bonus"),
                    applicable_positions=record.get("applicable_positions", ["ALL"]),
                    position_ids=record.get("position_ids", []),
                    source=record.get("source", "imported"),
                    season_year=record.get("season_year"),
                    is_active=True,
                )
            )

        db.add_all(new_rules)
        db.commit()
        print(f"Inserted {len(new_rules)} rules for league {league_id}")
    finally:
        db.close()


def parse_file(path: str, source_platform: str = "imported") -> list[dict]:
    with open(path, newline="", encoding="utf-8") as csvfile:
        content = csvfile.read()
    rules = parse_csv_rows_to_rules(content, source_platform=source_platform)
    return [rule.model_dump() for rule in rules]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python import_scoring_rules.py file.csv [league_id] [source_platform]", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    league_id = int(sys.argv[2]) if len(sys.argv) >= 3 and sys.argv[2] else None
    source_platform = sys.argv[3] if len(sys.argv) >= 4 else "imported"

    try:
        records = parse_file(path, source_platform=source_platform)
    except ScoringImportError as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        sys.exit(2)

    if league_id is None:
        for record in records:
            print(json.dumps(record))
        return

    insert_rules(league_id, records)


if __name__ == "__main__":
    main()
