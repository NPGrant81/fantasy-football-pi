"""Normalize extracted MFL HTML records/champions/awards CSVs.

This converts report-specific wide/legacy shapes into stable per-report
normalized datasets suitable for downstream analytics and import workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd


REPORT_TO_DATASET: dict[str, str] = {
    "league_champions": "html_league_champions_normalized",
    "league_awards": "html_league_awards_normalized",
    "franchise_records": "html_franchise_records_normalized",
    "player_records": "html_player_records_normalized",
    "matchup_records": "html_matchup_records_normalized",
    "all_time_series_records": "html_all_time_series_normalized",
    "season_records": "html_season_records_normalized",
    "career_records": "html_career_records_normalized",
    "record_streaks": "html_record_streaks_normalized",
}

DEFAULT_REPORT_KEYS = list(REPORT_TO_DATASET.keys())


@dataclass
class NormalizeSummary:
    input_root: str
    output_root: str
    files_processed: int
    files_skipped: int
    warnings: list[str]
    rows_written_by_dataset: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_root": self.input_root,
            "output_root": self.output_root,
            "files_processed": self.files_processed,
            "files_skipped": self.files_skipped,
            "warnings": self.warnings,
            "rows_written_by_dataset": self.rows_written_by_dataset,
        }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    # Handle common mojibake quote artifacts without mutating arbitrary text.
    text = text.replace("�", "")
    return text.strip() or None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"-?\d+", text)
    if not match:
        return None
    return int(match.group(0))


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_wlt(value: Any) -> tuple[int | None, int | None, int | None]:
    text = str(value or "").strip()
    if not text:
        return (None, None, None)
    match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*", text)
    if not match:
        return (None, None, None)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _extract_shared(row: pd.Series, report_key: str) -> dict[str, Any]:
    return {
        "season": _to_int(row.get("season")),
        "league_id": str(row.get("league_id") or "").strip() or None,
        "source_system": str(row.get("source_system") or "").strip() or None,
        "source_endpoint": str(row.get("source_endpoint") or report_key).strip() or report_key,
        "source_url": str(row.get("source_url") or "").strip() or None,
        "extracted_at_utc": str(row.get("extracted_at_utc") or "").strip() or None,
        "normalization_version": "v1",
    }


def _normalize_league_champions(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    year_prefixes = sorted(
        {
            column.split("_", 1)[0]
            for column in frame.columns
            if re.fullmatch(r"\d{4}_(place|franchise)", column)
        }
    )

    for _, source_row in frame.iterrows():
        shared = _extract_shared(source_row, "league_champions")
        for year_text in year_prefixes:
            place_col = f"{year_text}_place"
            franchise_col = f"{year_text}_franchise"
            place_text = _clean_text(source_row.get(place_col))
            franchise_raw = _clean_text(source_row.get(franchise_col))
            if not place_text and not franchise_raw:
                continue

            rows.append(
                {
                    **shared,
                    "champion_season": _to_int(year_text),
                    "place_text": place_text,
                    "place_rank": _to_int(place_text),
                    "franchise_name_raw": franchise_raw,
                    "franchise_name_clean": _clean_text(franchise_raw),
                }
            )

    return pd.DataFrame(rows)


def _normalize_league_awards(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, source_row in frame.iterrows():
        shared = _extract_shared(source_row, "league_awards")
        rows.append(
            {
                **shared,
                "award_season": _to_int(source_row.get("report_season")),
                "award_title": _clean_text(source_row.get("award_title")),
                "franchise_name_raw": _clean_text(source_row.get("franchise")),
                "franchise_name_clean": _clean_text(source_row.get("franchise")),
            }
        )
    return pd.DataFrame(rows)


def _normalize_franchise_records(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, source_row in frame.iterrows():
        shared = _extract_shared(source_row, "franchise_records")
        rows.append(
            {
                **shared,
                "record_rank": _to_int(source_row.get("value")),
                "franchise_name_raw": _clean_text(source_row.get("franchise")),
                "franchise_name_clean": _clean_text(source_row.get("franchise")),
                "record_year": _to_int(source_row.get("year")),
                "record_week": _to_int(source_row.get("week")),
                "points": _to_float(source_row.get("pts")),
            }
        )
    return pd.DataFrame(rows)


def _split_player_display(player_display: Any) -> tuple[str | None, str | None, str | None]:
    text = _clean_text(player_display)
    if not text:
        return (None, None, None)
    parts = text.split(" ")
    if len(parts) < 3:
        return (text, None, None)
    maybe_team = parts[-2]
    maybe_pos = parts[-1]
    if re.fullmatch(r"[A-Z]{2,3}", maybe_team) and re.fullmatch(r"[A-Za-z]{1,4}", maybe_pos):
        return (" ".join(parts[:-2]).strip() or text, maybe_team, maybe_pos.upper())
    return (text, None, None)


def _normalize_player_records(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, source_row in frame.iterrows():
        shared = _extract_shared(source_row, "player_records")
        player_raw = source_row.get("player")
        player_name, nfl_team, position = _split_player_display(player_raw)
        rows.append(
            {
                **shared,
                "record_rank": _to_int(source_row.get("value")),
                "overall_rank": _to_int(source_row.get("ovr")),
                "player_display_raw": _clean_text(player_raw),
                "player_name": player_name,
                "nfl_team": nfl_team,
                "position": position,
                "owner_context_raw": _clean_text(source_row.get("status")),
                "record_year": _to_int(source_row.get("year")),
                "record_week": _to_int(source_row.get("week")),
                "points": _to_float(source_row.get("pts")),
            }
        )
    return pd.DataFrame(rows)


def _normalize_matchup_records(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, source_row in frame.iterrows():
        shared = _extract_shared(source_row, "matchup_records")
        rows.append(
            {
                **shared,
                "record_rank": _to_int(source_row.get("value")),
                "away_franchise_raw": _clean_text(source_row.get("away_franchise")),
                "home_franchise_raw": _clean_text(source_row.get("home_franchise")),
                "away_points": _to_float(source_row.get("pts")),
                "home_points": _to_float(source_row.get("pts_1")),
                "record_year": _to_int(source_row.get("year")),
                "record_week": _to_int(source_row.get("week")),
                "combined_score": _to_float(source_row.get("combined_score")),
                "margin_of_victory": _to_float(source_row.get("margin_of_victory")),
            }
        )
    return pd.DataFrame(rows)


def _normalize_all_time_series_records(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    year_columns = sorted([column for column in frame.columns if re.fullmatch(r"\d{4}_w_l_t", column)])

    for _, source_row in frame.iterrows():
        shared = _extract_shared(source_row, "all_time_series_records")
        total_w_l_t = _clean_text(source_row.get("total_w_l_t"))
        total_pct = _to_float(source_row.get("pct"))
        opponent = _clean_text(source_row.get("opponent"))

        for year_col in year_columns:
            season_w_l_t_raw = _clean_text(source_row.get(year_col))
            if not season_w_l_t_raw:
                continue
            wins, losses, ties = _parse_wlt(season_w_l_t_raw)
            rows.append(
                {
                    **shared,
                    "opponent_franchise_raw": opponent,
                    "series_season": _to_int(year_col.split("_", 1)[0]),
                    "season_w_l_t_raw": season_w_l_t_raw,
                    "season_wins": wins,
                    "season_losses": losses,
                    "season_ties": ties,
                    "total_w_l_t_raw": total_w_l_t,
                    "total_pct": total_pct,
                }
            )
    return pd.DataFrame(rows)


def _normalize_season_records(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, source_row in frame.iterrows():
        shared = _extract_shared(source_row, "season_records")
        rows.append(
            {
                **shared,
                "record_rank": _to_int(source_row.get("value")),
                "franchise_name_raw": _clean_text(source_row.get("franchise")),
                "franchise_name_clean": _clean_text(source_row.get("franchise")),
                "record_year": _to_int(source_row.get("year")),
                "wins": _to_int(source_row.get("w")),
                "losses": _to_int(source_row.get("l")),
                "ties": _to_int(source_row.get("t")),
                "points_for": _to_float(source_row.get("pf")),
                "points_against": _to_float(source_row.get("pa")),
            }
        )
    return pd.DataFrame(rows)


def _normalize_career_records(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, source_row in frame.iterrows():
        shared = _extract_shared(source_row, "career_records")
        rows.append(
            {
                **shared,
                "record_rank": _to_int(source_row.get("value")),
                "franchise_name_raw": _clean_text(source_row.get("franchise")),
                "franchise_name_clean": _clean_text(source_row.get("franchise")),
                "wins": _to_int(source_row.get("w")),
                "losses": _to_int(source_row.get("l")),
                "ties": _to_int(source_row.get("t")),
                "win_pct": _to_float(source_row.get("pct")),
                "points_for": _to_float(source_row.get("pf")),
                "avg_points_for": _to_float(source_row.get("avg_pf")),
                "points_against": _to_float(source_row.get("pa")),
                "avg_points_against": _to_float(source_row.get("avg_pa")),
                "seasons_raw": _clean_text(source_row.get("seasons")),
            }
        )
    return pd.DataFrame(rows)


def _normalize_record_streaks(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, source_row in frame.iterrows():
        shared = _extract_shared(source_row, "record_streaks")
        rows.append(
            {
                **shared,
                "record_rank": _to_int(source_row.get("value")),
                "franchise_name_raw": _clean_text(source_row.get("franchise")),
                "franchise_name_clean": _clean_text(source_row.get("franchise")),
                "record_year": _to_int(source_row.get("year")),
                "start_week": _to_int(source_row.get("start_week")),
                "streak_length": _to_int(source_row.get("streak_length")),
                "streak_type": _clean_text(source_row.get("streak_type")),
            }
        )
    return pd.DataFrame(rows)


NORMALIZERS = {
    "league_champions": _normalize_league_champions,
    "league_awards": _normalize_league_awards,
    "franchise_records": _normalize_franchise_records,
    "player_records": _normalize_player_records,
    "matchup_records": _normalize_matchup_records,
    "all_time_series_records": _normalize_all_time_series_records,
    "season_records": _normalize_season_records,
    "career_records": _normalize_career_records,
    "record_streaks": _normalize_record_streaks,
}


def _write_frame(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def run_normalize_mfl_html_records(
    *,
    input_root: str,
    output_root: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    report_keys: list[str] | None = None,
) -> dict[str, Any]:
    in_root = Path(input_root)
    out_root = Path(output_root) if output_root else Path(f"{input_root}_normalized")
    selected_reports = report_keys or DEFAULT_REPORT_KEYS

    files_processed = 0
    files_skipped = 0
    warnings: list[str] = []
    rows_written_by_dataset = {dataset: 0 for dataset in REPORT_TO_DATASET.values()}

    if not in_root.exists():
        raise ValueError(f"input root does not exist: {in_root}")

    for report_key in selected_reports:
        if report_key not in REPORT_TO_DATASET:
            raise ValueError(f"unsupported report key: {report_key}")

        report_dir = in_root / report_key
        if not report_dir.exists():
            warnings.append(f"missing report directory: {report_dir}")
            continue

        dataset_name = REPORT_TO_DATASET[report_key]
        normalizer = NORMALIZERS[report_key]

        for source_csv in sorted(report_dir.glob("*.csv")):
            year = _to_int(source_csv.stem)
            if start_year is not None and (year is None or year < start_year):
                continue
            if end_year is not None and (year is None or year > end_year):
                continue

            try:
                frame = pd.read_csv(source_csv)
            except Exception as exc:  # noqa: BLE001
                files_skipped += 1
                warnings.append(f"failed reading {source_csv}: {exc}")
                continue

            if frame.empty:
                files_skipped += 1
                warnings.append(f"empty source file: {source_csv}")
                continue

            try:
                normalized = normalizer(frame)
                target_csv = out_root / dataset_name / source_csv.name
                _write_frame(target_csv, normalized)
                rows_written_by_dataset[dataset_name] += len(normalized)
                files_processed += 1
            except Exception as exc:  # noqa: BLE001
                files_skipped += 1
                warnings.append(f"failed normalizing {source_csv}: {exc}")

    summary = NormalizeSummary(
        input_root=str(in_root),
        output_root=str(out_root),
        files_processed=files_processed,
        files_skipped=files_skipped,
        warnings=warnings,
        rows_written_by_dataset=rows_written_by_dataset,
    )
    _write_json(out_root / "_normalize_summary.json", summary.to_dict())
    return summary.to_dict()
