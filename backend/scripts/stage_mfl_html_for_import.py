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
    "draftResults": ["season", "league_id", "franchise_id", "player_mfl_id", "round", "pick_number"],
}

# Columns required by the downstream importer (subset of REQUIRED_HEADERS).
IMPORTER_REQUIRED_HEADERS: dict[str, list[str]] = {
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


def _read_csv_rows_with_headers(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return headers, rows


def _write_csv_rows(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _read_league_id_for_season(*, api_root: Path, season: int) -> str:
    candidate_paths = [
        api_root / "league" / f"{season}.csv",
        api_root / "franchises" / f"{season}.csv",
        api_root / "players" / f"{season}.csv",
        api_root / "draftResults" / f"{season}.csv",
    ]
    for csv_path in candidate_paths:
        if not csv_path.exists():
            continue
        rows = _read_csv_rows(csv_path)
        if not rows:
            continue
        league_id = str(rows[0].get("league_id") or "").strip()
        if league_id:
            return league_id
    return ""


def _draft_override_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    """Deduplicate draft override rows by season+league+franchise+round+pick.

    Prefer the mapped player id when present so repeated staging runs stay
    stable even if staged rows do not include round/pick context.
    For auction picks (no round/pick and no player id yet), fall back to
    winning_bid as a discriminator to avoid collapsing multiple picks from
    the same franchise to a single key.
    """
    season = str(row.get("season") or "").strip()
    league_id = str(row.get("league_id") or "").strip()
    franchise_id = str(row.get("franchise_id") or "").strip()

    player_id = str(row.get("player_mfl_id") or "").strip()
    if player_id:
        return (season, league_id, franchise_id, player_id, "")

    rnd = str(row.get("round") or "").strip()
    pick = str(row.get("pick_number") or "").strip()
    if rnd or pick:
        return (season, league_id, franchise_id, rnd, pick)

    # Auction rows: no round/pick, use winning_bid to distinguish picks.
    winning_bid = str(row.get("winning_bid") or "").strip()
    return (season, league_id, franchise_id, winning_bid, "")


def _enrich_manual_draft_template_from_raw_json(
    *,
    api_root: Path,
    template_path: Path,
    season: int,
) -> int:
    """Pre-populate a manual override template with skeleton rows from raw API JSON.

    When MFL returns draft picks with franchise/round/pick but empty player IDs,
    this writes those skeleton rows into the template so the operator only needs
    to fill in the ``player_mfl_id`` column.  Returns the number of rows written.
    """
    raw_path = api_root / "raw" / "draftResults" / f"{season}.json"
    if not raw_path.exists():
        return 0

    try:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    picks = (
        payload.get("draftResults", {}).get("draftUnit", {}).get("draftPick", []) or []
    )
    if isinstance(picks, dict):
        picks = [picks]

    league_id = _read_league_id_for_season(api_root=api_root, season=season)
    skeleton_rows: list[dict[str, str]] = []
    for pick in picks:
        franchise_id = str(pick.get("franchise") or "").strip()
        rnd = str(pick.get("round") or "").strip()
        pick_number = str(pick.get("pick") or "").strip()
        if not franchise_id:
            continue
        skeleton_rows.append({
            "season": str(season),
            "league_id": league_id,
            "franchise_id": franchise_id,
            "player_mfl_id": "",
            "round": rnd,
            "pick_number": pick_number,
        })

    if not skeleton_rows:
        return 0

    _write_csv_rows(template_path, REQUIRED_HEADERS["draftResults"], skeleton_rows)
    return len(skeleton_rows)


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
    api_root: Path,
    output_root: Path,
    seasons: list[int],
    summary: StageSummary,
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
        # Manual override files are intentionally preserved even when overwrite=True,
        # because they contain operator-entered historical backfill data that must
        # not be discarded on a re-run.
        if manual_path.exists():
            continue

        skeleton_count = _enrich_manual_draft_template_from_raw_json(
            api_root=api_root,
            template_path=manual_path,
            season=season,
        )
        if skeleton_count == 0:
            _write_header_only_csv(manual_path, REQUIRED_HEADERS["draftResults"])
        summary.draft_results_manual_templates += 1
        label = f"{skeleton_count} skeleton rows" if skeleton_count else "header-only template"
        summary.warnings.append(
            f"draftResults season={season} has no player_mfl_id rows; created manual override template ({label}) at {manual_path}"
        )


def _merge_manual_draft_overrides(
    *,
    output_root: Path,
    seasons: list[int],
    summary: StageSummary,
) -> None:
    required = IMPORTER_REQUIRED_HEADERS["draftResults"]

    for season in seasons:
        draft_csv_path = output_root / "draftResults" / f"{season}.csv"
        manual_path = output_root / "manual_overrides" / "draftResults" / f"{season}.csv"
        if not draft_csv_path.exists() or not manual_path.exists():
            continue

        staged_headers, staged_rows = _read_csv_rows_with_headers(draft_csv_path)
        manual_headers, manual_rows = _read_csv_rows_with_headers(manual_path)
        output_headers = list(staged_headers)
        for column in manual_headers:
            if column and column not in output_headers:
                output_headers.append(column)
        for column in REQUIRED_HEADERS["draftResults"]:
            if column not in output_headers:
                output_headers.append(column)

        valid_manual_rows: list[dict[str, str]] = []

        for row in manual_rows:
            missing = [column for column in required if not str(row.get(column) or "").strip()]
            if missing:
                # Header-only templates read back as zero rows, so only warn on actual partial rows.
                if any(str(value or "").strip() for value in row.values()):
                    # Skeleton templates intentionally leave player ids blank until
                    # operators provide the historical backfill values.
                    if missing == ["player_mfl_id"]:
                        continue
                    summary.warnings.append(
                        f"manual override draftResults season={season} has row missing columns {missing}; row skipped"
                    )
                continue
            normalized_row = {column: str(row.get(column) or "").strip() for column in output_headers}
            valid_manual_rows.append(normalized_row)

        if not valid_manual_rows:
            continue

        merged_by_key = {
            _draft_override_key(row): {column: str(row.get(column) or "").strip() for column in output_headers}
            for row in staged_rows
        }
        for row in valid_manual_rows:
            merged_by_key[_draft_override_key(row)] = row

        merged_rows = list(merged_by_key.values())
        _write_csv_rows(draft_csv_path, output_headers, merged_rows)
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
        api_root=api_base,
        output_root=output_base,
        seasons=seasons,
        summary=summary,
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
