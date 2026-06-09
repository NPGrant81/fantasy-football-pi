"""CSV importer and migration helper for scoring rules."""

from __future__ import annotations

import os
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


LEGACY_CSV_ARCHIVE_ENV_FLAG = "FFPI_ALLOW_LEGACY_CSV_ARCHIVE"
LEGACY_CSV_ARCHIVE_CLI_FLAG = "--allow-legacy-csv-archive"


def legacy_csv_archive_opted_in(cli_flag_enabled: bool) -> bool:
    env_enabled = os.getenv(LEGACY_CSV_ARCHIVE_ENV_FLAG, "0") == "1"
    return bool(cli_flag_enabled and env_enabled)


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


def main(argv: list[str] | None = None) -> None:
    args = list(argv) if argv is not None else sys.argv[1:]

    allow_legacy_csv_archive = LEGACY_CSV_ARCHIVE_CLI_FLAG in args
    args = [arg for arg in args if arg != LEGACY_CSV_ARCHIVE_CLI_FLAG]

    if not legacy_csv_archive_opted_in(allow_legacy_csv_archive):
        print(
            "ERROR: import_scoring_rules.py is ARCHIVAL-ONLY and disabled by default.\n"
            "       Use DB-first scoring workflows instead.\n"
            f"       To run intentionally, set {LEGACY_CSV_ARCHIVE_ENV_FLAG}=1 and pass {LEGACY_CSV_ARCHIVE_CLI_FLAG}.",
            file=sys.stderr,
        )
        sys.exit(1)

    if len(args) < 1:
        print("Usage: python import_scoring_rules.py file.csv [league_id] [source_platform]", file=sys.stderr)
        sys.exit(1)

    path = args[0]
    league_id = int(args[1]) if len(args) >= 2 and args[1] else None
    source_platform = args[2] if len(args) >= 3 else "imported"

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
