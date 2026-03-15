"""Stage MFL HTML extraction outputs into an importer-compatible root.

The importer currently requires three canonical CSV domains:
- franchises
- players
- draftResults

HTML report extraction is valuable for legacy insights but does not directly
emit those three domains. This staging helper composes an import-ready root by
copying canonical API CSVs for each season and preserving HTML report CSVs
under a supplementary path for audit/analysis.
"""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_REPORT_TYPES: tuple[str, ...] = ("franchises", "players", "draftResults")

REQUIRED_HEADERS: dict[str, list[str]] = {
    "franchises": ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
    "players": ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
    "draftResults": ["season", "league_id", "franchise_id", "player_mfl_id"],
}


@dataclass
class StageSummary:
    seasons: list[int]
    api_root: str
    html_root: str
    output_root: str
    copied_required_files: int = 0
    scaffolded_required_files: int = 0
    copied_html_reports: int = 0
    draft_results_manual_templates: int = 0
    manual_override_rows_merged: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seasons": self.seasons,
            "api_root": self.api_root,
            "html_root": self.html_root,
            "output_root": self.output_root,
            "copied_required_files": self.copied_required_files,
            "scaffolded_required_files": self.scaffolded_required_files,
            "copied_html_reports": self.copied_html_reports,
            "draft_results_manual_templates": self.draft_results_manual_templates,
            "manual_override_rows_merged": self.manual_override_rows_merged,
            "warnings": self.warnings,
        }


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _copy_file(src: Path, dst: Path) -> None:
    _ensure_parent(dst)
    shutil.copy2(src, dst)


def _write_header_only_csv(path: Path, headers: list[str]) -> None:
    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _write_csv_rows(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _draft_override_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("season") or "").strip(),
        str(row.get("league_id") or "").strip(),
        str(row.get("franchise_id") or "").strip(),
        str(row.get("round") or "").strip(),
        str(row.get("pick_number") or "").strip(),
    )


def _stage_required_csvs(
    *,
    api_root: Path,
    output_root: Path,
    seasons: list[int],
    summary: StageSummary,
    overwrite: bool,
) -> None:
    for report_type in REQUIRED_REPORT_TYPES:
        for season in seasons:
            src = api_root / report_type / f"{season}.csv"
            dst = output_root / report_type / f"{season}.csv"

            if dst.exists() and not overwrite:
                continue

            if src.exists():
                _copy_file(src, dst)
                summary.copied_required_files += 1
                continue

            # When API CSV is unavailable, scaffolding avoids hard importer
            # missing-file failures and clearly signals zero extracted rows.
            headers = REQUIRED_HEADERS[report_type]
            _write_header_only_csv(dst, headers)
            summary.scaffolded_required_files += 1
            summary.warnings.append(f"missing API source for {report_type} season={season}; scaffolded header-only CSV")


def _stage_html_reports(
    *,
    html_root: Path,
    output_root: Path,
    seasons: list[int],
    summary: StageSummary,
    overwrite: bool,
) -> None:
    if not html_root.exists():
        summary.warnings.append(f"html_root not found: {html_root}")
        return

    for report_dir in html_root.iterdir():
        if not report_dir.is_dir() or report_dir.name == "raw":
            continue

        for season in seasons:
            src = report_dir / f"{season}.csv"
            if not src.exists():
                continue

            dst = output_root / "supplementary_html" / report_dir.name / f"{season}.csv"
            if dst.exists() and not overwrite:
                continue

            _copy_file(src, dst)
            summary.copied_html_reports += 1

    html_summary_src = html_root / "_run_summary.json"
    if html_summary_src.exists():
        _copy_file(html_summary_src, output_root / "supplementary_html" / "_html_run_summary.json")


def _ensure_draft_results_manual_fallback(
    *,
    output_root: Path,
    seasons: list[int],
    summary: StageSummary,
    overwrite: bool,
) -> None:
    for season in seasons:
        draft_csv_path = output_root / "draftResults" / f"{season}.csv"
        if not draft_csv_path.exists():
            continue

        has_player = False
        with draft_csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if str((row or {}).get("player_mfl_id") or "").strip():
                    has_player = True
                    break

        if has_player:
            continue

        manual_path = output_root / "manual_overrides" / "draftResults" / f"{season}.csv"
        if manual_path.exists():
            continue

        _write_header_only_csv(manual_path, REQUIRED_HEADERS["draftResults"])
        summary.draft_results_manual_templates += 1
        summary.warnings.append(
            f"draftResults season={season} has no player_mfl_id rows; created manual override template at {manual_path}"
        )


def _merge_manual_draft_overrides(
    *,
    output_root: Path,
    seasons: list[int],
    summary: StageSummary,
) -> None:
    required = REQUIRED_HEADERS["draftResults"]

    for season in seasons:
        draft_csv_path = output_root / "draftResults" / f"{season}.csv"
        manual_path = output_root / "manual_overrides" / "draftResults" / f"{season}.csv"
        if not draft_csv_path.exists() or not manual_path.exists():
            continue

        staged_rows = _read_csv_rows(draft_csv_path)
        manual_rows = _read_csv_rows(manual_path)
        valid_manual_rows: list[dict[str, str]] = []

        for row in manual_rows:
            missing = [column for column in required if not str(row.get(column) or "").strip()]
            if missing:
                # Header-only templates read back as zero rows, so only warn on actual partial rows.
                if any(str(value or "").strip() for value in row.values()):
                    summary.warnings.append(
                        f"manual override draftResults season={season} has row missing columns {missing}; row skipped"
                    )
                continue
            valid_manual_rows.append({column: str(row.get(column) or "").strip() for column in required})

        if not valid_manual_rows:
            continue

        merged_by_key = {_draft_override_key(row): {column: str(row.get(column) or "").strip() for column in required} for row in staged_rows}
        for row in valid_manual_rows:
            merged_by_key[_draft_override_key(row)] = row

        merged_rows = list(merged_by_key.values())
        _write_csv_rows(draft_csv_path, required, merged_rows)
        summary.manual_override_rows_merged += len(valid_manual_rows)


def run_stage_mfl_html_for_import(
    *,
    start_year: int,
    end_year: int,
    api_root: str,
    html_root: str,
    output_root: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    seasons = list(range(start_year, end_year + 1))
    api_base = Path(api_root)
    html_base = Path(html_root)
    output_base = Path(output_root)

    summary = StageSummary(
        seasons=seasons,
        api_root=str(api_base),
        html_root=str(html_base),
        output_root=str(output_base),
    )

    _stage_required_csvs(
        api_root=api_base,
        output_root=output_base,
        seasons=seasons,
        summary=summary,
        overwrite=overwrite,
    )
    _stage_html_reports(
        html_root=html_base,
        output_root=output_base,
        seasons=seasons,
        summary=summary,
        overwrite=overwrite,
    )
    _ensure_draft_results_manual_fallback(
        output_root=output_base,
        seasons=seasons,
        summary=summary,
        overwrite=overwrite,
    )
    _merge_manual_draft_overrides(
        output_root=output_base,
        seasons=seasons,
        summary=summary,
    )

    output_base.mkdir(parents=True, exist_ok=True)
    (output_base / "_stage_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2),
        encoding="utf-8",
    )
    return summary.to_dict()
