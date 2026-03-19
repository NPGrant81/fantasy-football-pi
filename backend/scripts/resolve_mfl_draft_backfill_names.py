"""Resolve player ids in draft backfill sheets from manual player-name entries."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


KNOWN_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
    "PK",
    "DEF",
    "DL",
    "DB",
    "LB",
    "K",
}


@dataclass
class ResolveSummary:
    input_root: str
    sheet_root: str
    seasons: list[int]
    apply_changes: bool
    rows_seen: int = 0
    rows_matched: int = 0
    rows_already_filled: int = 0
    rows_skipped_no_manual_name: int = 0
    rows_unmatched: int = 0
    rows_ambiguous: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_root": self.input_root,
            "sheet_root": self.sheet_root,
            "seasons": self.seasons,
            "apply_changes": self.apply_changes,
            "rows_seen": self.rows_seen,
            "rows_matched": self.rows_matched,
            "rows_already_filled": self.rows_already_filled,
            "rows_skipped_no_manual_name": self.rows_skipped_no_manual_name,
            "rows_unmatched": self.rows_unmatched,
            "rows_ambiguous": self.rows_ambiguous,
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


def _clean_manual_player_name(value: str) -> str:
    cleaned = str(value or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s*\(R\)\s*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _parse_manual_player_name(value: str) -> tuple[str, str, str]:
    """Parse 'Lastname, Firstname TEAM POS' into name/team/pos hints."""
    cleaned = _clean_manual_player_name(value)
    if not cleaned or cleaned.lower() in {"no pick made", "pick skipped by commissioner"}:
        return "", "", ""

    parts = cleaned.split(" ")
    if len(parts) < 2:
        return cleaned, "", ""

    pos = ""
    team = ""
    if parts[-1].upper() in KNOWN_POSITIONS:
        pos = parts[-1].upper()
        parts = parts[:-1]
    if parts and re.fullmatch(r"[A-Z]{2,3}|FA", parts[-1].upper()):
        team = parts[-1].upper()
        parts = parts[:-1]

    name = " ".join(parts).strip()
    return name, team, pos


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def run_resolve_mfl_draft_backfill_names(
    *,
    input_root: str,
    start_year: int,
    end_year: int,
    sheet_root: str | None = None,
    apply_changes: bool = False,
) -> dict[str, Any]:
    seasons = list(range(start_year, end_year + 1))
    input_base = Path(input_root)
    sheets_base = Path(sheet_root) if sheet_root else input_base / "manual_overrides" / "draft_backfill_sheets"

    summary = ResolveSummary(
        input_root=str(input_base),
        sheet_root=str(sheets_base),
        seasons=seasons,
        apply_changes=apply_changes,
    )

    review_headers = [
        "season",
        "franchise_id",
        "draft_style",
        "round",
        "pick_number",
        "manual_player_name",
        "parsed_name",
        "parsed_team",
        "parsed_position",
        "resolution_status",
        "candidate_ids",
        "candidate_names",
    ]
    review_rows: list[dict[str, str]] = []

    for season in seasons:
        sheet_path = sheets_base / f"{season}.csv"
        players_path = input_base / "players" / f"{season}.csv"

        if not sheet_path.exists():
            summary.warnings.append(f"season={season} sheet missing: {sheet_path}")
            continue

        sheet_rows = _read_csv_rows(sheet_path)
        player_rows = _read_csv_rows(players_path)
        if not player_rows:
            summary.warnings.append(f"season={season} players snapshot missing/empty: {players_path}")

        by_name: dict[str, list[dict[str, str]]] = {}
        by_triplet: dict[tuple[str, str, str], list[dict[str, str]]] = {}
        for p in player_rows:
            name = _norm(p.get("player_name", ""))
            team = str(p.get("nfl_team") or "").strip().upper()
            pos = str(p.get("position") or "").strip().upper()
            if not name:
                continue
            by_name.setdefault(name, []).append(p)
            by_triplet.setdefault((name, team, pos), []).append(p)

        changed = False
        for row in sheet_rows:
            summary.rows_seen += 1

            existing_id = str(row.get("player_mfl_id") or "").strip()
            if existing_id:
                summary.rows_already_filled += 1
                continue

            manual_name = str(row.get("manual_player_name") or "").strip()
            if not manual_name:
                summary.rows_skipped_no_manual_name += 1
                continue

            parsed_name, parsed_team, parsed_pos = _parse_manual_player_name(manual_name)
            if not parsed_name:
                summary.rows_unmatched += 1
                continue

            candidates = []
            if parsed_team and parsed_pos:
                candidates = by_triplet.get((_norm(parsed_name), parsed_team, parsed_pos), [])
            if not candidates:
                candidates = by_name.get(_norm(parsed_name), [])

            candidate_ids = " | ".join(str(c.get("player_mfl_id") or "").strip() for c in candidates if str(c.get("player_mfl_id") or "").strip())
            # Player names are usually "Lastname, Firstname", so avoid comma joins.
            candidate_names = " | ".join(str(c.get("player_name") or "").strip() for c in candidates)

            status = ""
            if len(candidates) == 1:
                resolved_id = str(candidates[0].get("player_mfl_id") or "").strip()
                if resolved_id:
                    row["player_mfl_id"] = resolved_id
                    row["player_name_hint"] = str(candidates[0].get("player_name") or "").strip()
                    row["position_hint"] = str(candidates[0].get("position") or "").strip()
                    row["nfl_team_hint"] = str(candidates[0].get("nfl_team") or "").strip()
                    summary.rows_matched += 1
                    changed = True
                    status = "matched"
                else:
                    summary.rows_unmatched += 1
                    status = "unmatched"
            elif len(candidates) > 1:
                summary.rows_ambiguous += 1
                status = "ambiguous"
            else:
                summary.rows_unmatched += 1
                status = "unmatched"

            if status in {"ambiguous", "unmatched"}:
                review_rows.append(
                    {
                        "season": str(row.get("season") or ""),
                        "franchise_id": str(row.get("franchise_id") or ""),
                        "draft_style": str(row.get("draft_style") or ""),
                        "round": str(row.get("round") or ""),
                        "pick_number": str(row.get("pick_number") or ""),
                        "manual_player_name": manual_name,
                        "parsed_name": parsed_name,
                        "parsed_team": parsed_team,
                        "parsed_position": parsed_pos,
                        "resolution_status": status,
                        "candidate_ids": candidate_ids,
                        "candidate_names": candidate_names,
                    }
                )

        if apply_changes and changed:
            headers = list(sheet_rows[0].keys()) if sheet_rows else []
            if headers:
                _write_csv_rows(sheet_path, headers, sheet_rows)

    summary_path = sheets_base / "_backfill_name_resolve_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")

    review_path = sheets_base / "_backfill_name_resolve_review.csv"
    _write_csv_rows(review_path, review_headers, review_rows)

    return summary.to_dict()
