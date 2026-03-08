from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.scripts.import_scoring_rules import insert_rules, parse_file

CSV_PATH = "backend/data/scoring_logic.csv"
LEAGUE_ID = 1


def import_scoring_logic(league_id: int = LEAGUE_ID, csv_path: str = CSV_PATH) -> None:
    records = parse_file(csv_path, source_platform="legacy_csv")
    insert_rules(league_id, records)
    print(f"Imported scoring logic for league {league_id} from {csv_path}")


if __name__ == "__main__":
    import_scoring_logic()
