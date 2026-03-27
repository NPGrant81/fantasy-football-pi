"""
One-time seed: import canonical scoring rules from CSV into the scoring_rules table.

Safe to run multiple times — the script checks whether any scoring rules already
exist for the given league_id and, if so, skips seeding entirely. This avoids
creating duplicates but will not partially fill or repair previously seeded data;
to re-import, delete existing rules for the league first.

Usage:
    python seed_scoring_rules.py [league_id]

    league_id defaults to 60 (Post Pacific League).

After running this script successfully you can delete:
    backend/data/scoring_logic.csv
    backend/data/scoring_logic_import_canonical.csv
    backend/data/scoring_logic_import_ready.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.database import SessionLocal
import backend.models as models
from backend.services.scoring_import_service import (
    ScoringImportError,
    parse_csv_rows_to_rules,
)

# Path to the canonical import-ready file in backend/data/
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CSV_PATH = _DATA_DIR / "scoring_logic_import_ready.csv"

DEFAULT_LEAGUE_ID = 60


def seed(league_id: int = DEFAULT_LEAGUE_ID) -> None:
    if not _CSV_PATH.exists():
        print(f"CSV not found at {_CSV_PATH} — nothing to seed.")
        return

    with _CSV_PATH.open(encoding="utf-8") as f:
        content = f.read()

    try:
        rules = parse_csv_rows_to_rules(content, source_platform="canonical")
    except ScoringImportError as exc:
        print(f"Failed to parse CSV: {exc}", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        # Ensure the league row exists so the FK isn't violated.
        league = db.query(models.League).filter(models.League.id == league_id).first()
        if league is None:
            league = models.League(id=league_id, name=f"League {league_id}")
            db.add(league)
            db.flush()

        existing_count = (
            db.query(models.ScoringRule)
            .filter(models.ScoringRule.league_id == league_id)
            .count()
        )
        if existing_count > 0:
            print(
                f"Scoring rules already seeded for league {league_id} "
                f"({existing_count} rows present) — skipping.\n"
                f"To re-import, delete existing rules first:\n"
                f"  DELETE FROM scoring_rules WHERE league_id = {league_id};"
            )
            return

        to_insert = [
            models.ScoringRule(
                league_id=league_id,
                category=r.category,
                event_name=r.event_name,
                description=r.description,
                range_min=r.range_min,
                range_max=r.range_max,
                point_value=r.point_value,
                calculation_type=r.calculation_type,
                applicable_positions=r.applicable_positions,
                position_ids=r.position_ids,
                source=r.source or "canonical",
                season_year=r.season_year,
                is_active=True,
            )
            for r in rules
        ]

        db.add_all(to_insert)
        db.commit()
        print(
            f"Seeded {len(to_insert)} scoring rules for league {league_id}.\n"
            "\nYou can now safely delete:\n"
            "  backend/data/scoring_logic.csv\n"
            "  backend/data/scoring_logic_import_canonical.csv\n"
            "  backend/data/scoring_logic_import_ready.csv"
        )
    finally:
        db.close()


def main() -> None:
    league_id = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LEAGUE_ID
    seed(league_id)


if __name__ == "__main__":
    main()
