"""
One-time seed: load per-owner draft budgets from draft_budget.csv into the
draft_budgets table (DraftBudget model).

Intended for one-time or single-process use — each (league_id, owner_id, year)
combination is checked for existence before insert; if a matching row already
exists it is skipped.

Usage:
    python seed_draft_budgets.py [league_id]

    league_id defaults to 60 (Post Pacific League).

After running this script you can delete:
    backend/data/draft_budget.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.database import SessionLocal
import backend.models as models

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CSV_PATH = _DATA_DIR / "draft_budget.csv"

DEFAULT_LEAGUE_ID = 60


def _clean_money(val: str) -> float:
    return float(str(val).replace("$", "").replace(",", "").strip())


def seed(league_id: int = DEFAULT_LEAGUE_ID) -> None:
    if not _CSV_PATH.exists():
        print(f"CSV not found at {_CSV_PATH} — nothing to seed.")
        return

    rows: list[dict] = []
    with _CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    db = SessionLocal()
    try:
        # Build a set of owner IDs that actually exist in the users table so we
        # can skip rows whose foreign key would be violated.
        from sqlalchemy import text as sa_text

        existing_user_ids = {
            r[0]
            for r in db.execute(sa_text("SELECT id FROM users")).fetchall()
        }

        inserted = 0
        skipped = 0
        missing_owners: set[int] = set()
        for row in rows:
            owner_id = int(float(row["OwnerID"]))
            year = int(float(row["Year"]))
            budget = int(_clean_money(row["DraftBudget"]))

            if owner_id not in existing_user_ids:
                missing_owners.add(owner_id)
                skipped += 1
                continue

            existing = (
                db.query(models.DraftBudget)
                .filter(
                    models.DraftBudget.league_id == league_id,
                    models.DraftBudget.owner_id == owner_id,
                    models.DraftBudget.year == year,
                )
                .first()
            )
            if existing:
                skipped += 1
                continue

            db.add(
                models.DraftBudget(
                    league_id=league_id,
                    owner_id=owner_id,
                    year=year,
                    total_budget=budget,
                )
            )
            inserted += 1

        db.commit()
        print(
            f"Draft budgets seeded for league {league_id}: "
            f"{inserted} inserted, {skipped} already present or skipped."
        )
        if missing_owners:
            print(
                f"\nWARNING: {len(missing_owners)} owner IDs from the CSV are not in the users table "
                f"and were skipped: {sorted(missing_owners)}\n"
                "The users table must already be populated (the DB is the source of truth). "
                "load_ppl_history.py is archival-only and requires an explicit opt-in; "
                "do not run it unless rebuilding from scratch after a deliberate full-reset."
            )
        if inserted > 0:
            print(
                "\nYou can now safely delete:\n"
                "  backend/data/draft_budget.csv"
            )
    finally:
        db.close()


def main() -> None:
    league_id = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LEAGUE_ID
    seed(league_id)


if __name__ == "__main__":
    main()
