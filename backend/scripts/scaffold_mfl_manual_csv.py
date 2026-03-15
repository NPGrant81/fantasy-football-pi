"""Scaffold manual CSV templates for legacy MFL seasons.

This supports seasons where API extraction is blocked by legacy host
resolution issues (for example 2002-2003 redirect behavior).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPORT_COLUMNS: dict[str, list[str]] = {
    "franchises": [
        "season",
        "league_id",
        "source_system",
        "source_endpoint",
        "extracted_at_utc",
        "franchise_id",
        "franchise_name",
        "owner_name",
        "owner_email",
        "division",
    ],
    "players": [
        "season",
        "league_id",
        "source_system",
        "source_endpoint",
        "extracted_at_utc",
        "player_mfl_id",
        "player_name",
        "position",
        "nfl_team",
        "status",
    ],
    "draftResults": [
        "season",
        "league_id",
        "source_system",
        "source_endpoint",
        "extracted_at_utc",
        "franchise_id",
        "player_mfl_id",
        "pick_number",
        "round",
        "winning_bid",
        "is_keeper_pick",
    ],
}


@dataclass
class ScaffoldSummary:
    output_root: str
    seasons: list[int]
    report_types: list[str]
    files_created: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_root": self.output_root,
            "seasons": self.seasons,
            "report_types": self.report_types,
            "files_created": self.files_created,
        }


def _write_header(path: Path, headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)


def run_scaffold_mfl_manual_csv(
    *,
    start_year: int,
    end_year: int,
    output_root: str = "exports/history_manual",
    report_types: list[str] | None = None,
) -> dict[str, Any]:
    selected_report_types = report_types or ["franchises", "players", "draftResults"]
    seasons = list(range(start_year, end_year + 1))

    files_created = 0
    root = Path(output_root)

    for report_type in selected_report_types:
        headers = REPORT_COLUMNS.get(report_type)
        if headers is None:
            raise ValueError(f"unsupported report type for manual scaffold: {report_type}")

        for season in seasons:
            path = root / report_type / f"{season}.csv"
            if not path.exists():
                _write_header(path, headers)
                files_created += 1

    return ScaffoldSummary(
        output_root=str(root),
        seasons=seasons,
        report_types=selected_report_types,
        files_created=files_created,
    ).to_dict()