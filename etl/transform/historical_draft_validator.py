from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = ["league_id", "year", "owner_id", "player_id", "round_num", "pick_num"]


@dataclass
class DraftValidationResult:
    validated_draft_results: pd.DataFrame
    validation_report: dict[str, Any]
    correction_ledger: pd.DataFrame


def _validate_columns(df: pd.DataFrame, required: list[str]) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def validate_historical_draft_results(
    draft_df: pd.DataFrame,
    *,
    players_df: pd.DataFrame | None = None,
    owners_df: pd.DataFrame | None = None,
) -> DraftValidationResult:
    _validate_columns(draft_df, REQUIRED_COLUMNS)

    working = draft_df.copy()
    for column in ["league_id", "year", "owner_id", "player_id", "round_num", "pick_num"]:
        working[column] = pd.to_numeric(working[column], errors="coerce")

    ledger_rows: list[dict[str, Any]] = []

    critical_null_mask = working[["league_id", "year", "owner_id", "player_id"]].isna().any(axis=1)
    if critical_null_mask.any():
        for row_index in working[critical_null_mask].index:
            ledger_rows.append(
                {
                    "row_index": int(row_index),
                    "field": "critical_keys",
                    "old_value": "null",
                    "new_value": "null",
                    "action": "unresolved",
                    "reason": "missing_critical_reference",
                }
            )

    working["league_id"] = working["league_id"].fillna(-1).astype(int)
    working["year"] = working["year"].fillna(-1).astype(int)
    working["owner_id"] = working["owner_id"].fillna(-1).astype(int)
    working["player_id"] = working["player_id"].fillna(-1).astype(int)
    working["round_num"] = working["round_num"].fillna(0).astype(int)
    working["pick_num"] = working["pick_num"].fillna(0).astype(int)

    duplicate_key = ["league_id", "year", "round_num", "pick_num"]
    duplicate_mask = working.duplicated(subset=duplicate_key, keep=False)
    duplicate_rows = int(duplicate_mask.sum())
    if duplicate_rows:
        for row_index in working[duplicate_mask].index:
            ledger_rows.append(
                {
                    "row_index": int(row_index),
                    "field": "league_year_round_pick",
                    "old_value": "duplicate",
                    "new_value": "duplicate",
                    "action": "flagged",
                    "reason": "duplicate_pick_slot",
                }
            )

    unresolved_owner_count = int((working["owner_id"] <= 0).sum())
    unresolved_player_count = int((working["player_id"] <= 0).sum())

    if players_df is not None and not players_df.empty and "id" in players_df.columns:
        known_players = set(pd.to_numeric(players_df["id"], errors="coerce").dropna().astype(int).tolist())
        unknown_player_rows = working[~working["player_id"].isin(known_players) & (working["player_id"] > 0)]
        for row_index in unknown_player_rows.index:
            ledger_rows.append(
                {
                    "row_index": int(row_index),
                    "field": "player_id",
                    "old_value": int(working.at[row_index, "player_id"]),
                    "new_value": int(working.at[row_index, "player_id"]),
                    "action": "flagged",
                    "reason": "unknown_player_reference",
                }
            )

    if owners_df is not None and not owners_df.empty and "id" in owners_df.columns:
        known_owners = set(pd.to_numeric(owners_df["id"], errors="coerce").dropna().astype(int).tolist())
        unknown_owner_rows = working[~working["owner_id"].isin(known_owners) & (working["owner_id"] > 0)]
        for row_index in unknown_owner_rows.index:
            ledger_rows.append(
                {
                    "row_index": int(row_index),
                    "field": "owner_id",
                    "old_value": int(working.at[row_index, "owner_id"]),
                    "new_value": int(working.at[row_index, "owner_id"]),
                    "action": "flagged",
                    "reason": "unknown_owner_reference",
                }
            )

    keeper_column = "is_keeper" if "is_keeper" in working.columns else None
    if keeper_column is None:
        working["is_keeper"] = False
    else:
        working["is_keeper"] = working[keeper_column].fillna(False).astype(bool)

    year_counts = working.groupby("year").size().to_dict()
    year_completeness = {str(int(year)): int(count) for year, count in year_counts.items() if int(year) > 0}

    working["validation_status"] = "ok"
    working.loc[critical_null_mask, "validation_status"] = "critical_unresolved"
    working.loc[duplicate_mask, "validation_status"] = "duplicate_pick"
    working.loc[(working["owner_id"] <= 0) | (working["player_id"] <= 0), "validation_status"] = "critical_unresolved"

    report = {
        "total_rows": int(working.shape[0]),
        "critical_unresolved_reference_count": int((working["validation_status"] == "critical_unresolved").sum()),
        "critical_unresolved_reference_by_type": {
            "owner_id": unresolved_owner_count,
            "player_id": unresolved_player_count,
        },
        "duplicate_pick_count": duplicate_rows,
        "missing_pick_count": int(((working["round_num"] <= 0) | (working["pick_num"] <= 0)).sum()),
        "year_completeness": year_completeness,
        "keeper_labeling_summary": {
            "keeper_rows": int(working["is_keeper"].sum()),
            "non_keeper_rows": int((~working["is_keeper"]).sum()),
            "confidence_notes": "Derived from source is_keeper where available; defaults to False when absent.",
        },
    }

    correction_ledger = pd.DataFrame(
        ledger_rows,
        columns=["row_index", "field", "old_value", "new_value", "action", "reason"],
    )

    return DraftValidationResult(
        validated_draft_results=working,
        validation_report=report,
        correction_ledger=correction_ledger,
    )


def write_draft_validation_outputs(
    result: DraftValidationResult,
    validated_csv_path: str | Path,
    report_json_path: str | Path,
    correction_ledger_csv_path: str | Path,
) -> None:
    validated_csv_path = Path(validated_csv_path)
    report_json_path = Path(report_json_path)
    correction_ledger_csv_path = Path(correction_ledger_csv_path)

    validated_csv_path.parent.mkdir(parents=True, exist_ok=True)
    report_json_path.parent.mkdir(parents=True, exist_ok=True)
    correction_ledger_csv_path.parent.mkdir(parents=True, exist_ok=True)

    result.validated_draft_results.to_csv(validated_csv_path, index=False)
    report_json_path.write_text(json.dumps(result.validation_report, indent=2), encoding="utf-8")
    result.correction_ledger.to_csv(correction_ledger_csv_path, index=False)
