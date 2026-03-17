"""Apply completed draft backfill sheets into staged manual override CSVs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MANUAL_HEADERS = [
    "season",
    "league_id",
    "franchise_id",
    "player_mfl_id",
    "round",
    "pick_number",
    "winning_bid",
    "is_keeper_pick",
]

BLOCKED_2002_SOURCE_MARKERS = (
    "myfantasyleague.com/2002/options",
    "api.myfantasyleague.com/2002/export?type=draftresults",
    "api.myfantasyleague.com/2002/export?type=auctionresults",
)


@dataclass
class BackfillApplySummary:
    input_root: str
    sheet_root: str
    seasons: list[int]
    apply_changes: bool
    require_source_url: bool
    sheets_missing: int = 0
    candidate_rows: int = 0
    rows_updated: int = 0
    rows_appended: int = 0
    rows_skipped_missing_player_id: int = 0
    rows_skipped_missing_source_url: int = 0
    rows_skipped_blocked_source_policy: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_root": self.input_root,
            "sheet_root": self.sheet_root,
            "seasons": self.seasons,
            "apply_changes": self.apply_changes,
            "require_source_url": self.require_source_url,
            "sheets_missing": self.sheets_missing,
            "candidate_rows": self.candidate_rows,
            "rows_updated": self.rows_updated,
            "rows_appended": self.rows_appended,
            "rows_skipped_missing_player_id": self.rows_skipped_missing_player_id,
            "rows_skipped_missing_source_url": self.rows_skipped_missing_source_url,
            "rows_skipped_blocked_source_policy": self.rows_skipped_blocked_source_policy,
            "warnings": self.warnings,
        }


def _is_blocked_2002_source(source_url: str) -> bool:
    normalized = source_url.strip().lower()
    if not normalized:
        return False
    if not any(marker in normalized for marker in BLOCKED_2002_SOURCE_MARKERS):
        return False
    return ("o=17" in normalized) or ("type=draftresults" in normalized) or ("type=auctionresults" in normalized)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv_rows(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _row_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("season") or "").strip(),
        str(row.get("league_id") or "").strip(),
        str(row.get("franchise_id") or "").strip(),
        str(row.get("round") or "").strip(),
        str(row.get("pick_number") or "").strip(),
    )


def _normalize_manual_row(sheet_row: dict[str, str]) -> dict[str, str]:
    return {
        "season": str(sheet_row.get("season") or "").strip(),
        "league_id": str(sheet_row.get("league_id") or "").strip(),
        "franchise_id": str(sheet_row.get("franchise_id") or "").strip(),
        "player_mfl_id": str(sheet_row.get("player_mfl_id") or "").strip(),
        "round": str(sheet_row.get("round") or "").strip(),
        "pick_number": str(sheet_row.get("pick_number") or "").strip(),
        "winning_bid": str(sheet_row.get("winning_bid") or "").strip(),
        "is_keeper_pick": "",
    }


def run_apply_mfl_draft_backfill_sheet(
    *,
    input_root: str,
    start_year: int,
    end_year: int,
    sheet_root: str | None = None,
    apply_changes: bool = False,
    require_source_url: bool = False,
    enforce_2002_source_policy: bool = True,
) -> dict[str, Any]:
    seasons = list(range(start_year, end_year + 1))
    input_base = Path(input_root)
    sheets_base = Path(sheet_root) if sheet_root else input_base / "manual_overrides" / "draft_backfill_sheets"

    summary = BackfillApplySummary(
        input_root=str(input_base),
        sheet_root=str(sheets_base),
        seasons=seasons,
        apply_changes=apply_changes,
        require_source_url=require_source_url,
    )

    for season in seasons:
        sheet_path = sheets_base / f"{season}.csv"
        manual_path = input_base / "manual_overrides" / "draftResults" / f"{season}.csv"
        if not sheet_path.exists():
            summary.sheets_missing += 1
            summary.warnings.append(f"season={season} sheet missing: {sheet_path}")
            continue

        sheet_rows = _read_csv_rows(sheet_path)
        manual_rows = _read_csv_rows(manual_path)

        manual_by_key = {_row_key(row): dict(row) for row in manual_rows}
        season_updated = 0
        season_appended = 0

        for row in sheet_rows:
            player_id = str(row.get("player_mfl_id") or "").strip()
            if not player_id:
                summary.rows_skipped_missing_player_id += 1
                continue

            source_url = str(row.get("manual_source_url") or "").strip()
            if require_source_url and not source_url:
                summary.rows_skipped_missing_source_url += 1
                continue

            if enforce_2002_source_policy and str(row.get("season") or "").strip() == "2002":
                if not source_url:
                    summary.rows_skipped_missing_source_url += 1
                    summary.warnings.append(
                        "season=2002 skipped because manual_source_url is required by 2002 source policy"
                    )
                    continue
                if _is_blocked_2002_source(source_url):
                    summary.rows_skipped_blocked_source_policy += 1
                    summary.warnings.append(
                        "season=2002 skipped because source URL matches known blocked legacy draft feed"
                    )
                    continue

            normalized = _normalize_manual_row(row)
            key = _row_key(normalized)

            # Fallback key when sheets omit round/pick context.
            if not key[3] and not key[4]:
                key = (
                    normalized["season"],
                    normalized["league_id"],
                    normalized["franchise_id"],
                    "",
                    "",
                )

            summary.candidate_rows += 1
            existing = manual_by_key.get(key)
            if existing is None:
                manual_by_key[key] = normalized
                season_appended += 1
                continue

            if str(existing.get("player_mfl_id") or "").strip() != normalized["player_mfl_id"]:
                existing["player_mfl_id"] = normalized["player_mfl_id"]
                if normalized["winning_bid"]:
                    existing["winning_bid"] = normalized["winning_bid"]
                if normalized["round"]:
                    existing["round"] = normalized["round"]
                if normalized["pick_number"]:
                    existing["pick_number"] = normalized["pick_number"]
                season_updated += 1

        if apply_changes and (season_updated or season_appended or not manual_path.exists()):
            output_rows = list(manual_by_key.values())
            # Stable order by season/franchise/round/pick for easier diffs.
            output_rows.sort(
                key=lambda r: (
                    str(r.get("season") or ""),
                    str(r.get("franchise_id") or ""),
                    str(r.get("round") or ""),
                    str(r.get("pick_number") or ""),
                )
            )
            _write_csv_rows(manual_path, MANUAL_HEADERS, output_rows)

        summary.rows_updated += season_updated
        summary.rows_appended += season_appended

    (sheets_base / "_backfill_apply_summary.json").parent.mkdir(parents=True, exist_ok=True)
    (sheets_base / "_backfill_apply_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2), encoding="utf-8"
    )
    return summary.to_dict()
