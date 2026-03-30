from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_EVENT_COLUMNS = ["league_id", "season", "owner_id", "event_ts", "event_type"]


@dataclass
class BudgetTimelineResult:
    timeline: pd.DataFrame
    reconciliation_report: dict[str, Any]
    owner_mapping_exceptions: pd.DataFrame


def _validate_columns(df: pd.DataFrame, required: list[str]) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def build_owner_budget_timeline(
    events_df: pd.DataFrame,
    *,
    start_budget: float = 200.0,
) -> BudgetTimelineResult:
    _validate_columns(events_df, REQUIRED_EVENT_COLUMNS)

    working = events_df.copy()
    working["league_id"] = pd.to_numeric(working["league_id"], errors="coerce")
    working["season"] = pd.to_numeric(working["season"], errors="coerce")
    working["owner_id"] = pd.to_numeric(working["owner_id"], errors="coerce")
    working = working.dropna(subset=["league_id", "season", "owner_id"]).copy()

    if working.empty:
        empty_timeline = pd.DataFrame(
            columns=[
                "league_id",
                "season",
                "owner_id",
                "event_ts",
                "event_type",
                "delta_budget",
                "spent_to_date",
                "remaining_budget",
            ]
        )
        return BudgetTimelineResult(
            timeline=empty_timeline,
            reconciliation_report={
                "rows": 0,
                "reconciliation_pass_rate": 1.0,
                "failed_rows": 0,
                "negative_budget_rows": 0,
                "null_rate_required_fields": 0.0,
                "outlier_rows": 0,
            },
            owner_mapping_exceptions=pd.DataFrame(columns=["league_id", "season", "owner_id", "reason"]),
        )

    working["league_id"] = working["league_id"].astype(int)
    working["season"] = working["season"].astype(int)
    working["owner_id"] = working["owner_id"].astype(int)
    working["event_ts"] = pd.to_datetime(working["event_ts"], errors="coerce", utc=True)
    working["event_type"] = working["event_type"].fillna("").astype(str).str.strip().str.lower()

    # Negative values consume budget; positive values refund budget.
    if "delta_budget" in working.columns:
        working["delta_budget"] = pd.to_numeric(working["delta_budget"], errors="coerce").fillna(0.0)
    else:
        bid_series = pd.to_numeric(working.get("winning_bid", 0.0), errors="coerce").fillna(0.0)
        working["delta_budget"] = -bid_series

    working = working.sort_values(
        ["league_id", "season", "owner_id", "event_ts", "event_type"],
        ascending=[True, True, True, True, True],
    ).reset_index(drop=True)

    working["spent_to_date"] = (
        working.groupby(["league_id", "season", "owner_id"])["delta_budget"].cumsum().abs()
    )
    working["remaining_budget"] = (start_budget + working.groupby(["league_id", "season", "owner_id"])["delta_budget"].cumsum()).round(2)

    owner_mapping_exceptions = working[working["owner_id"] <= 0][["league_id", "season", "owner_id"]].copy()
    owner_mapping_exceptions["reason"] = "invalid_owner_id"

    required = ["league_id", "season", "owner_id", "event_ts", "event_type", "delta_budget"]
    null_cells = int(working[required].isna().sum().sum())
    total_cells = max(1, int(working.shape[0] * len(required)))
    null_rate = round(null_cells / total_cells, 6)

    failed_rows = int(working["remaining_budget"].isna().sum())
    negative_budget_rows = int((working["remaining_budget"] < 0).sum())
    outlier_rows = int((working["delta_budget"].abs() > start_budget).sum())
    pass_rate = round(1.0 - ((failed_rows + negative_budget_rows) / max(1, len(working))), 6)

    timeline = working[
        [
            "league_id",
            "season",
            "owner_id",
            "event_ts",
            "event_type",
            "delta_budget",
            "spent_to_date",
            "remaining_budget",
        ]
    ].copy()

    report = {
        "rows": int(timeline.shape[0]),
        "reconciliation_pass_rate": max(0.0, min(1.0, pass_rate)),
        "failed_rows": failed_rows,
        "negative_budget_rows": negative_budget_rows,
        "null_rate_required_fields": null_rate,
        "outlier_rows": outlier_rows,
    }

    return BudgetTimelineResult(
        timeline=timeline,
        reconciliation_report=report,
        owner_mapping_exceptions=owner_mapping_exceptions,
    )


def write_budget_timeline_outputs(
    result: BudgetTimelineResult,
    timeline_csv_path: str | Path,
    report_json_path: str | Path,
    exceptions_csv_path: str | Path,
) -> None:
    timeline_csv_path = Path(timeline_csv_path)
    report_json_path = Path(report_json_path)
    exceptions_csv_path = Path(exceptions_csv_path)
    timeline_csv_path.parent.mkdir(parents=True, exist_ok=True)
    report_json_path.parent.mkdir(parents=True, exist_ok=True)
    exceptions_csv_path.parent.mkdir(parents=True, exist_ok=True)

    result.timeline.to_csv(timeline_csv_path, index=False)
    report_json_path.write_text(json.dumps(result.reconciliation_report, indent=2), encoding="utf-8")
    result.owner_mapping_exceptions.to_csv(exceptions_csv_path, index=False)
