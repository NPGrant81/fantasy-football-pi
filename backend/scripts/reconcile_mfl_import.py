"""Reconcile MFL CSV sources against imported database rows.

Issue #259 baseline:
- Compare source CSV row counts vs database import outcomes by season.
- Emit mismatch details for audit and rerun decisions.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import func

from backend import models
from backend.database import SessionLocal


REQUIRED_COLUMNS: dict[str, list[str]] = {
    "franchises": ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
    "players": ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
    "draftResults": ["season", "league_id", "franchise_id", "player_mfl_id"],
}


@dataclass
class CsvReportCount:
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "invalid_rows": self.invalid_rows,
        }


@dataclass
class SeasonReconciliation:
    season: int
    source_counts: dict[str, CsvReportCount]
    db_counts: dict[str, int]
    checks: dict[str, bool]
    mismatches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "season": self.season,
            "source_counts": {k: v.to_dict() for k, v in self.source_counts.items()},
            "db_counts": self.db_counts,
            "checks": self.checks,
            "mismatches": self.mismatches,
        }


@dataclass
class ReconciliationSummary:
    input_root: str
    target_league_id: int
    seasons: list[int]
    season_reports: list[SeasonReconciliation]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        mismatch_count = sum(len(report.mismatches) for report in self.season_reports)
        return {
            "input_root": self.input_root,
            "target_league_id": self.target_league_id,
            "seasons": self.seasons,
            "mismatch_count": mismatch_count,
            "season_reports": [report.to_dict() for report in self.season_reports],
            "warnings": self.warnings,
        }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _csv_count_for_season(
    *,
    input_root: Path,
    season: int,
    report_type: str,
    warnings: list[str],
) -> CsvReportCount:
    path = input_root / report_type / f"{season}.csv"
    result = CsvReportCount()

    if not path.exists():
        warnings.append(f"missing file: {path}")
        return result

    required = REQUIRED_COLUMNS[report_type]
    for row in _read_csv(path):
        result.total_rows += 1
        missing = [col for col in required if (row.get(col) or "").strip() == ""]
        if missing:
            result.invalid_rows += 1
            continue
        result.valid_rows += 1

    return result


def _db_counts_for_season(*, season: int, target_league_id: int) -> dict[str, int]:
    session_id = f"MFL_{season}"
    db = SessionLocal()
    try:
        base = db.query(models.DraftPick).filter(
            models.DraftPick.league_id == target_league_id,
            models.DraftPick.year == season,
            models.DraftPick.session_id == session_id,
        )

        draft_picks = int(base.with_entities(func.count(models.DraftPick.id)).scalar() or 0)
        distinct_owners = int(base.with_entities(func.count(func.distinct(models.DraftPick.owner_id))).scalar() or 0)
        distinct_players = int(base.with_entities(func.count(func.distinct(models.DraftPick.player_id))).scalar() or 0)

        return {
            "draft_picks": draft_picks,
            "distinct_owners": distinct_owners,
            "distinct_players": distinct_players,
        }
    finally:
        db.close()


def run_reconcile_mfl_import(
    *,
    input_root: str,
    target_league_id: int,
    start_year: int,
    end_year: int,
    output_json: str | None = None,
) -> dict[str, Any]:
    seasons = list(range(start_year, end_year + 1))
    warnings: list[str] = []
    reports: list[SeasonReconciliation] = []
    root = Path(input_root)

    for season in seasons:
        source_counts = {
            "franchises": _csv_count_for_season(
                input_root=root,
                season=season,
                report_type="franchises",
                warnings=warnings,
            ),
            "players": _csv_count_for_season(
                input_root=root,
                season=season,
                report_type="players",
                warnings=warnings,
            ),
            "draftResults": _csv_count_for_season(
                input_root=root,
                season=season,
                report_type="draftResults",
                warnings=warnings,
            ),
        }
        db_counts = _db_counts_for_season(season=season, target_league_id=target_league_id)

        checks = {
            "draft_results_vs_draft_picks": source_counts["draftResults"].valid_rows == db_counts["draft_picks"],
            "franchises_vs_distinct_owners": source_counts["franchises"].valid_rows == db_counts["distinct_owners"],
            "players_vs_distinct_players": source_counts["players"].valid_rows == db_counts["distinct_players"],
        }

        mismatches: list[str] = []
        if not checks["draft_results_vs_draft_picks"]:
            mismatches.append(
                "draftResults valid_rows does not match imported draft_picks count "
                f"({source_counts['draftResults'].valid_rows} vs {db_counts['draft_picks']})"
            )
        if not checks["franchises_vs_distinct_owners"]:
            mismatches.append(
                "franchises valid_rows does not match imported distinct owners "
                f"({source_counts['franchises'].valid_rows} vs {db_counts['distinct_owners']})"
            )
        if not checks["players_vs_distinct_players"]:
            mismatches.append(
                "players valid_rows does not match imported distinct players "
                f"({source_counts['players'].valid_rows} vs {db_counts['distinct_players']})"
            )

        reports.append(
            SeasonReconciliation(
                season=season,
                source_counts=source_counts,
                db_counts=db_counts,
                checks=checks,
                mismatches=mismatches,
            )
        )

    summary = ReconciliationSummary(
        input_root=input_root,
        target_league_id=target_league_id,
        seasons=seasons,
        season_reports=reports,
        warnings=warnings,
    ).to_dict()

    if output_json:
        output_path = Path(output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return summary