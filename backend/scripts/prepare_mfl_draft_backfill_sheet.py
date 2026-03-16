"""Prepare fill-ready draft backfill sheets from staged MFL import roots.

The output sheets are designed for operator completion when legacy seasons
lack player ids in draft payloads. Rows are annotated with draft style so snake
and auction workflows can be handled differently.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BackfillSheetSummary:
    input_root: str
    output_root: str
    seasons: list[int]
    sheets_written: int = 0
    rows_written: int = 0
    rows_skipped_already_filled: int = 0
    style_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_root": self.input_root,
            "output_root": self.output_root,
            "seasons": self.seasons,
            "sheets_written": self.sheets_written,
            "rows_written": self.rows_written,
            "rows_skipped_already_filled": self.rows_skipped_already_filled,
            "style_counts": self.style_counts,
            "warnings": self.warnings,
        }


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


def _draft_style_for_row(row: dict[str, str]) -> str:
    explicit = str(row.get("draft_style") or "").strip().lower()
    if explicit in {"snake", "auction"}:
        return explicit

    if str(row.get("winning_bid") or "").strip():
        return "auction"

    if str(row.get("round") or "").strip() or str(row.get("pick_number") or "").strip():
        return "snake"

    return "unknown"


def _style_hint(style: str) -> str:
    if style == "snake":
        return "Use season draft board order (round/pick) to map franchise pick to player id"
    if style == "auction":
        return "Use auction ledger (bid/timestamp/franchise) to map winning bid player id"
    return "Use any authoritative league artifact to map franchise selection to player id"


def _row_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("season") or "").strip(),
        str(row.get("league_id") or "").strip(),
        str(row.get("franchise_id") or "").strip(),
        str(row.get("round") or "").strip(),
        str(row.get("pick_number") or "").strip(),
    )


def run_prepare_mfl_draft_backfill_sheet(
    *,
    input_root: str,
    start_year: int,
    end_year: int,
    output_root: str | None = None,
    include_filled: bool = False,
) -> dict[str, Any]:
    seasons = list(range(start_year, end_year + 1))
    input_base = Path(input_root)
    output_base = Path(output_root) if output_root else input_base / "manual_overrides" / "draft_backfill_sheets"

    summary = BackfillSheetSummary(
        input_root=str(input_base),
        output_root=str(output_base),
        seasons=seasons,
    )

    headers = [
        "season",
        "league_id",
        "franchise_id",
        "franchise_name",
        "draft_style",
        "round",
        "pick_number",
        "winning_bid",
        "player_mfl_id",
        "player_name_hint",
        "position_hint",
        "nfl_team_hint",
        "hint_strategy",
        "manual_player_name",
        "manual_source_url",
        "manual_notes",
    ]

    for season in seasons:
        manual_path = input_base / "manual_overrides" / "draftResults" / f"{season}.csv"
        draft_path = input_base / "draftResults" / f"{season}.csv"
        franchises_path = input_base / "franchises" / f"{season}.csv"
        players_path = input_base / "players" / f"{season}.csv"

        manual_rows = _read_csv_rows(manual_path)
        draft_rows = _read_csv_rows(draft_path)
        franchise_rows = _read_csv_rows(franchises_path)
        player_rows = _read_csv_rows(players_path)

        franchise_name_by_id = {
            str(row.get("franchise_id") or "").strip(): str(row.get("franchise_name") or "").strip()
            for row in franchise_rows
            if str(row.get("franchise_id") or "").strip()
        }
        player_by_id = {
            str(row.get("player_mfl_id") or "").strip(): row
            for row in player_rows
            if str(row.get("player_mfl_id") or "").strip()
        }
        draft_by_key = {_row_key(row): row for row in draft_rows}

        # Prefer manual rows; fall back to draft rows when templates are absent.
        seed_rows = manual_rows or draft_rows
        if not seed_rows:
            summary.warnings.append(f"season={season} has no draft/manual rows to prepare")
            continue

        output_rows: list[dict[str, str]] = []
        for row in seed_rows:
            player_id = str(row.get("player_mfl_id") or "").strip()
            if player_id and not include_filled:
                summary.rows_skipped_already_filled += 1
                continue

            key = _row_key(row)
            source_row = draft_by_key.get(key, row)
            style = _draft_style_for_row(source_row)
            franchise_id = str(source_row.get("franchise_id") or row.get("franchise_id") or "").strip()
            player_hint = player_by_id.get(player_id, {}) if player_id else {}

            output_rows.append(
                {
                    "season": str(source_row.get("season") or row.get("season") or season).strip(),
                    "league_id": str(source_row.get("league_id") or row.get("league_id") or "").strip(),
                    "franchise_id": franchise_id,
                    "franchise_name": franchise_name_by_id.get(franchise_id, ""),
                    "draft_style": style,
                    "round": str(source_row.get("round") or row.get("round") or "").strip(),
                    "pick_number": str(source_row.get("pick_number") or row.get("pick_number") or "").strip(),
                    "winning_bid": str(source_row.get("winning_bid") or row.get("winning_bid") or "").strip(),
                    "player_mfl_id": player_id,
                    "player_name_hint": str(player_hint.get("player_name") or "").strip(),
                    "position_hint": str(player_hint.get("position") or "").strip(),
                    "nfl_team_hint": str(player_hint.get("nfl_team") or "").strip(),
                    "hint_strategy": _style_hint(style),
                    "manual_player_name": "",
                    "manual_source_url": "",
                    "manual_notes": "",
                }
            )
            summary.style_counts[style] = summary.style_counts.get(style, 0) + 1

        out_path = output_base / f"{season}.csv"
        _write_csv_rows(out_path, headers, output_rows)
        summary.sheets_written += 1
        summary.rows_written += len(output_rows)

    output_base.mkdir(parents=True, exist_ok=True)
    (output_base / "_backfill_sheet_summary.json").write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
    return summary.to_dict()
