from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


def _parse_dollars(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"[^0-9.-]", "", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def build_owner_budget_timeline(
    draft_budget_df: pd.DataFrame,
    draft_results_df: pd.DataFrame,
    users_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    budget_rows = draft_budget_df.copy()
    budget_rows["owner_id"] = budget_rows["OwnerID"].apply(lambda x: int(x) if str(x).strip().isdigit() else None)
    budget_rows["season_year"] = budget_rows["Year"].apply(lambda x: int(x) if str(x).strip().isdigit() else None)
    budget_rows["starting_budget"] = budget_rows["DraftBudget"].apply(_parse_dollars)
    budget_rows = budget_rows.dropna(subset=["owner_id", "season_year", "starting_budget"]).copy()

    owner_lookup = (
        users_df.copy()
        .assign(owner_id=lambda df: pd.to_numeric(df["OwnerID"], errors="coerce"))
        .dropna(subset=["owner_id"])
    )
    owner_lookup["owner_id"] = owner_lookup["owner_id"].astype(int)
    owner_lookup = owner_lookup.sort_values(by=["owner_id", "OwnerName"], kind="mergesort")
    owner_lookup = owner_lookup.drop_duplicates(subset=["owner_id"], keep="first")
    owner_name_by_id = dict(zip(owner_lookup["owner_id"], owner_lookup["OwnerName"]))

    draft_rows = draft_results_df.copy().reset_index().rename(columns={"index": "event_sequence"})
    draft_rows["owner_id"] = pd.to_numeric(draft_rows["OwnerID"], errors="coerce")
    draft_rows["season_year"] = pd.to_numeric(draft_rows["Year"], errors="coerce")
    draft_rows["winning_bid"] = draft_rows["WinningBid"].apply(_parse_dollars)
    draft_rows = draft_rows.dropna(subset=["owner_id", "season_year", "winning_bid"]).copy()
    draft_rows["owner_id"] = draft_rows["owner_id"].astype(int)
    draft_rows["season_year"] = draft_rows["season_year"].astype(int)

    grouped_budget = (
        budget_rows.sort_values(by=["season_year", "owner_id"], kind="mergesort")
        .drop_duplicates(subset=["season_year", "owner_id"], keep="last")
        [["season_year", "owner_id", "starting_budget"]]
    )

    timeline_rows: list[dict[str, Any]] = []
    exception_rows: list[dict[str, Any]] = []

    for (season_year, owner_id), owner_events in draft_rows.groupby(["season_year", "owner_id"], sort=True):
        budget_match = grouped_budget[
            (grouped_budget["season_year"] == season_year) & (grouped_budget["owner_id"] == owner_id)
        ]
        if budget_match.empty:
            exception_rows.append(
                {
                    "season_year": int(season_year),
                    "owner_id": int(owner_id),
                    "issue_type": "missing_starting_budget",
                    "detail": "No DraftBudget row found for owner-season",
                }
            )
            continue

        starting_budget = float(budget_match.iloc[-1]["starting_budget"])
        owner_name = str(owner_name_by_id.get(int(owner_id), f"Owner {owner_id}"))
        spend_cumulative = 0.0

        ordered_events = owner_events.sort_values(by=["event_sequence"], kind="mergesort")
        for _, event in ordered_events.iterrows():
            winning_bid = float(event["winning_bid"])
            spend_cumulative += winning_bid
            remaining_budget = starting_budget - spend_cumulative

            timeline_rows.append(
                {
                    "season_year": int(season_year),
                    "owner_id": int(owner_id),
                    "owner_name": owner_name,
                    "event_sequence": int(event["event_sequence"]),
                    "player_id": int(event["PlayerID"]) if str(event.get("PlayerID", "")).isdigit() else None,
                    "winning_bid": round(winning_bid, 2),
                    "cumulative_spend": round(spend_cumulative, 2),
                    "starting_budget": round(starting_budget, 2),
                    "remaining_budget": round(remaining_budget, 2),
                    "overspent": remaining_budget < 0,
                }
            )

        if spend_cumulative > starting_budget:
            exception_rows.append(
                {
                    "season_year": int(season_year),
                    "owner_id": int(owner_id),
                    "issue_type": "overspent_budget",
                    "detail": f"spent={spend_cumulative:.2f} > budget={starting_budget:.2f}",
                }
            )

    timeline_df = pd.DataFrame(timeline_rows).sort_values(
        by=["season_year", "owner_id", "event_sequence"], kind="mergesort"
    ) if timeline_rows else pd.DataFrame(columns=[
        "season_year",
        "owner_id",
        "owner_name",
        "event_sequence",
        "player_id",
        "winning_bid",
        "cumulative_spend",
        "starting_budget",
        "remaining_budget",
        "overspent",
    ])

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "timeline_rows": int(len(timeline_df)),
        "owner_season_pairs": int(timeline_df[["season_year", "owner_id"]].drop_duplicates().shape[0]) if not timeline_df.empty else 0,
        "overspent_owner_seasons": int(timeline_df[timeline_df["overspent"]][["season_year", "owner_id"]].drop_duplicates().shape[0]) if not timeline_df.empty else 0,
        "exceptions": exception_rows,
    }

    return timeline_df, report


def write_budget_timeline_outputs(
    draft_budget_csv: Path,
    draft_results_csv: Path,
    users_csv: Path,
    output_dir: Path,
) -> dict[str, Any]:
    draft_budget_df = pd.read_csv(draft_budget_csv)
    draft_results_df = pd.read_csv(draft_results_csv)
    users_df = pd.read_csv(users_csv)

    timeline_df, report = build_owner_budget_timeline(draft_budget_df, draft_results_df, users_df)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "budget_timeline_v1.csv"
    report_path = output_dir / "budget_timeline_report_v1.json"

    timeline_df.to_csv(csv_path, index=False)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return {
        "csv": str(csv_path),
        "report": str(report_path),
        "rows": int(len(timeline_df)),
        "exceptions": int(len(report.get("exceptions", []))),
    }
