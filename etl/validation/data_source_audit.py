"""Data source audit helpers for Issue #102 schema normalization.

This module inventories core CSV sources, normalizes header names to snake_case,
and validates key relationships between player/owner/position/year fields.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATASET_FILES = {
    "draft_results": "draft_results.csv",
    "yearly_results": "historical_rankings.csv",
    "player_id": "players.csv",
    "position_id": "positions.csv",
    "budget": "draft_budget.csv",
    "owner_registry": "teams.csv",
    "draft_strategy": "draft_strategy.csv",
}


@dataclass
class DatasetAudit:
    name: str
    file_path: str
    exists: bool
    row_count: int
    raw_headers: list[str]
    normalized_headers: list[str]



def _to_snake_case(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", (value or "").strip())
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", cleaned)
    snake = re.sub(r"_+", "_", snake).strip("_").lower()
    return snake



def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                headers = list(reader.fieldnames or [])
                rows = [dict(row) for row in reader]
            return headers, rows
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return [], []



def _resolve_column(headers: list[str], candidates: list[str]) -> str | None:
    lowered = {h.lower(): h for h in headers}
    for candidate in candidates:
        match = lowered.get(candidate.lower())
        if match:
            return match
    return None



def _collect_values(rows: list[dict[str, str]], column: str | None) -> set[str]:
    if not column:
        return set()
    values = set()
    for row in rows:
        value = (row.get(column) or "").strip()
        if value:
            values.add(value)
    return values



def _normalize_year_value(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None

    if text.isdigit():
        year = int(text)
        return year if 2000 <= year <= 2100 else None

    # Accept common legacy date forms like 1/1/2024 or 2024-01-01.
    date_match = re.search(r"(19|20)\d{2}", text)
    if not date_match:
        return None

    year = int(date_match.group(0))
    return year if 2000 <= year <= 2100 else None



def _collect_values_by_year(
    rows: list[dict[str, str]], value_column: str | None, year_column: str | None
) -> dict[int, set[str]]:
    if not value_column or not year_column:
        return {}

    values_by_year: dict[int, set[str]] = {}
    for row in rows:
        value = (row.get(value_column) or "").strip()
        year = _normalize_year_value(row.get(year_column) or "")
        if not value or year is None:
            continue
        values_by_year.setdefault(year, set()).add(value)

    return values_by_year



def _row_count_with_invalid_year(rows: list[dict[str, str]], year_column: str | None) -> int:
    if not year_column:
        return 0
    invalid = 0
    for row in rows:
        value = (row.get(year_column) or "").strip()
        if not value:
            continue
        if _normalize_year_value(value) is None:
            invalid += 1
    return invalid



def audit_sources(data_dir: Path) -> dict[str, Any]:
    data_dir = data_dir.resolve()

    datasets: dict[str, DatasetAudit] = {}
    dataset_rows: dict[str, list[dict[str, str]]] = {}

    for dataset_name, filename in DATASET_FILES.items():
        csv_path = data_dir / filename
        if not csv_path.exists():
            datasets[dataset_name] = DatasetAudit(
                name=dataset_name,
                file_path=str(csv_path),
                exists=False,
                row_count=0,
                raw_headers=[],
                normalized_headers=[],
            )
            dataset_rows[dataset_name] = []
            continue

        headers, rows = _read_csv_rows(csv_path)
        datasets[dataset_name] = DatasetAudit(
            name=dataset_name,
            file_path=str(csv_path),
            exists=True,
            row_count=len(rows),
            raw_headers=headers,
            normalized_headers=[_to_snake_case(col) for col in headers],
        )
        dataset_rows[dataset_name] = rows

    draft_headers = datasets["draft_results"].raw_headers
    players_headers = datasets["player_id"].raw_headers
    positions_headers = datasets["position_id"].raw_headers
    budget_headers = datasets["budget"].raw_headers

    draft_player_col = _resolve_column(draft_headers, ["PlayerID", "Player_ID", "player_id"])
    draft_owner_col = _resolve_column(draft_headers, ["OwnerID", "owner_id"])
    draft_position_col = _resolve_column(draft_headers, ["PositionID", "position_id"])
    draft_year_col = _resolve_column(draft_headers, ["Year", "year", "season"])

    players_id_col = _resolve_column(players_headers, ["Player_ID", "PlayerID", "player_id"])
    positions_id_col = _resolve_column(positions_headers, ["PositionID", "position_id"])
    positions_status_col = _resolve_column(positions_headers, ["PositionStatus", "status", "position_status"])
    budget_owner_col = _resolve_column(budget_headers, ["OwnerID", "owner_id"])
    budget_year_col = _resolve_column(budget_headers, ["Year", "year", "season"])

    draft_player_ids = _collect_values(dataset_rows["draft_results"], draft_player_col)
    player_ids = _collect_values(dataset_rows["player_id"], players_id_col)
    draft_position_ids = _collect_values(dataset_rows["draft_results"], draft_position_col)
    position_ids = _collect_values(dataset_rows["position_id"], positions_id_col)
    draft_owner_ids_by_year = _collect_values_by_year(
        dataset_rows["draft_results"], draft_owner_col, draft_year_col
    )
    budget_owner_ids_by_year = _collect_values_by_year(
        dataset_rows["budget"], budget_owner_col, budget_year_col
    )

    active_position_ids: set[str] = set()
    if positions_id_col and positions_status_col:
        for row in dataset_rows["position_id"]:
            status = (row.get(positions_status_col) or "").strip().lower()
            pos_id = (row.get(positions_id_col) or "").strip()
            if status == "active" and pos_id:
                active_position_ids.add(pos_id)

    missing_player_refs = sorted(draft_player_ids - player_ids)
    missing_position_refs = sorted(draft_position_ids - position_ids)
    inactive_position_refs = sorted(draft_position_ids - active_position_ids) if active_position_ids else []
    overlapping_years = sorted(
        set(draft_owner_ids_by_year.keys()).intersection(budget_owner_ids_by_year.keys())
    )
    owner_mismatch_set: set[str] = set()
    for year in overlapping_years:
        owner_mismatch_set.update(
            draft_owner_ids_by_year[year].symmetric_difference(budget_owner_ids_by_year[year])
        )

    owner_id_mismatch = sorted(owner_mismatch_set)

    draft_invalid_year_count = _row_count_with_invalid_year(dataset_rows["draft_results"], draft_year_col)
    budget_invalid_year_count = _row_count_with_invalid_year(dataset_rows["budget"], budget_year_col)

    missing_files = [name for name, dataset in datasets.items() if not dataset.exists]

    report = {
        "summary": {
            "data_dir": str(data_dir),
            "dataset_count": len(datasets),
            "missing_dataset_files": missing_files,
        },
        "datasets": {
            name: {
                "file_path": audit.file_path,
                "exists": audit.exists,
                "row_count": audit.row_count,
                "raw_headers": audit.raw_headers,
                "normalized_headers": audit.normalized_headers,
            }
            for name, audit in datasets.items()
        },
        "identifier_audit": {
            "missing_player_references_in_player_id": missing_player_refs,
            "missing_position_references_in_position_id": missing_position_refs,
            "inactive_or_unknown_position_ids_in_draft_results": inactive_position_refs,
            "owner_id_mismatch_between_draft_results_and_budget": owner_id_mismatch,
            "draft_results_invalid_year_rows": draft_invalid_year_count,
            "budget_invalid_year_rows": budget_invalid_year_count,
        },
    }
    return report



def report_to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = report.get("summary", {})
    datasets = report.get("datasets", {})
    id_audit = report.get("identifier_audit", {})

    lines.append("# Issue #102 Data Source Audit")
    lines.append("")
    lines.append(f"- Data directory: {summary.get('data_dir', '')}")
    lines.append(f"- Dataset count: {summary.get('dataset_count', 0)}")
    lines.append(
        f"- Missing files: {', '.join(summary.get('missing_dataset_files', [])) or 'None'}"
    )
    lines.append("")

    lines.append("## Dataset Inventory")
    lines.append("")
    lines.append("| Dataset | Exists | Rows | Headers |")
    lines.append("|---|---:|---:|---|")
    for dataset_name, details in datasets.items():
        headers = ", ".join(details.get("raw_headers", []))
        lines.append(
            f"| {dataset_name} | {str(details.get('exists', False)).lower()} | {details.get('row_count', 0)} | {headers} |"
        )
    lines.append("")

    lines.append("## Identifier Audit")
    lines.append("")
    lines.append(
        f"- Missing player refs in `player_id`: {len(id_audit.get('missing_player_references_in_player_id', []))}"
    )
    lines.append(
        f"- Missing position refs in `position_id`: {len(id_audit.get('missing_position_references_in_position_id', []))}"
    )
    lines.append(
        "- Inactive/unknown position refs used in draft results: "
        f"{len(id_audit.get('inactive_or_unknown_position_ids_in_draft_results', []))}"
    )
    lines.append(
        "- Owner ID mismatches (draft vs budget): "
        f"{len(id_audit.get('owner_id_mismatch_between_draft_results_and_budget', []))}"
    )
    lines.append(
        f"- Draft results invalid year rows: {id_audit.get('draft_results_invalid_year_rows', 0)}"
    )
    lines.append(
        f"- Budget invalid year rows: {id_audit.get('budget_invalid_year_rows', 0)}"
    )
    lines.append("")

    return "\n".join(lines)



def run_default_audit() -> tuple[dict[str, Any], str]:
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / "backend" / "data"
    report = audit_sources(data_dir)
    markdown = report_to_markdown(report)
    return report, markdown



def main() -> None:
    report, markdown = run_default_audit()

    repo_root = Path(__file__).resolve().parents[2]
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "issue102_data_audit.json"
    md_path = repo_root / "docs" / "DATA_SOURCE_AUDIT_ISSUE_102.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")

    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")


if __name__ == "__main__":
    main()
