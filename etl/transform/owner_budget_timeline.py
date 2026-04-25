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


def _parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def _resolve_starting_budget(
    *,
    owner_id: int,
    season_year: int,
    owner_budget_years: dict[int, list[tuple[int, float]]],
    global_budget_default: float,
) -> tuple[float, str, int | None]:
    owner_rows = owner_budget_years.get(owner_id, [])
    if not owner_rows:
        return float(global_budget_default), "global_default", None

    for year, amount in owner_rows:
        if year == season_year:
            return float(amount), "exact", year

    prior_rows = [(year, amount) for year, amount in owner_rows if year < season_year]
    if prior_rows:
        year, amount = max(prior_rows, key=lambda row: row[0])
        return float(amount), "carry_forward", int(year)

    future_rows = [(year, amount) for year, amount in owner_rows if year > season_year]
    if future_rows:
        year, amount = min(future_rows, key=lambda row: row[0])
        return float(amount), "carry_backward", int(year)

    return float(global_budget_default), "global_default", None


def build_owner_budget_timeline(
    draft_budget_df: pd.DataFrame,
    draft_results_df: pd.DataFrame,
    users_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    budget_rows = draft_budget_df.copy()
    budget_rows["owner_id"] = pd.to_numeric(budget_rows["OwnerID"], errors="coerce")
    budget_rows["season_year"] = pd.to_numeric(budget_rows["Year"], errors="coerce")
    budget_rows["starting_budget"] = budget_rows["DraftBudget"].apply(_parse_dollars)
    budget_rows = budget_rows.dropna(subset=["owner_id", "season_year", "starting_budget"]).copy()
    budget_rows["owner_id"] = budget_rows["owner_id"].astype(int)
    budget_rows["season_year"] = budget_rows["season_year"].astype(int)

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

    owner_budget_years: dict[int, list[tuple[int, float]]] = {}
    for _, row in grouped_budget.iterrows():
        owner_id = int(row["owner_id"])
        season_year = int(row["season_year"])
        starting_budget = float(row["starting_budget"])
        owner_budget_years.setdefault(owner_id, []).append((season_year, starting_budget))
    for owner_id in owner_budget_years:
        owner_budget_years[owner_id] = sorted(owner_budget_years[owner_id], key=lambda item: item[0])

    global_budget_default = float(grouped_budget["starting_budget"].median()) if not grouped_budget.empty else 200.0

    budget_resolution_counts = {
        "exact": 0,
        "carry_forward": 0,
        "carry_backward": 0,
        "global_default": 0,
    }

    timeline_rows: list[dict[str, Any]] = []
    exception_rows: list[dict[str, Any]] = []

    for (season_year, owner_id), owner_events in draft_rows.groupby(["season_year", "owner_id"], sort=True):
        starting_budget, budget_source, source_season_year = _resolve_starting_budget(
            owner_id=int(owner_id),
            season_year=int(season_year),
            owner_budget_years=owner_budget_years,
            global_budget_default=global_budget_default,
        )
        budget_resolution_counts[budget_source] = int(budget_resolution_counts.get(budget_source, 0) + 1)
        if budget_source != "exact":
            exception_rows.append(
                {
                    "season_year": int(season_year),
                    "owner_id": int(owner_id),
                    "issue_type": "budget_imputed",
                    "detail": (
                        f"source={budget_source}; "
                        + (f"source_season_year={source_season_year}" if source_season_year is not None else "source_season_year=None")
                    ),
                }
            )

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
                    "player_id": _parse_int(event.get("PlayerID")),
                    "winning_bid": round(winning_bid, 2),
                    "cumulative_spend": round(spend_cumulative, 2),
                    "starting_budget": round(starting_budget, 2),
                    "remaining_budget": round(remaining_budget, 2),
                    "overspent": remaining_budget < 0,
                    "budget_source": budget_source,
                    "source_season_year": source_season_year,
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
        "budget_source",
        "source_season_year",
    ])

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "timeline_rows": int(len(timeline_df)),
        "owner_season_pairs": int(timeline_df[["season_year", "owner_id"]].drop_duplicates().shape[0]) if not timeline_df.empty else 0,
        "overspent_owner_seasons": int(timeline_df[timeline_df["overspent"]][["season_year", "owner_id"]].drop_duplicates().shape[0]) if not timeline_df.empty else 0,
        "budget_resolution_counts": {str(k): int(v) for k, v in budget_resolution_counts.items()},
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

    return write_budget_timeline_outputs_from_dataframes(
        draft_budget_df=draft_budget_df,
        draft_results_df=draft_results_df,
        users_df=users_df,
        output_dir=output_dir,
    )


def write_budget_timeline_outputs_from_dataframes(
    *,
    draft_budget_df: pd.DataFrame,
    draft_results_df: pd.DataFrame,
    users_df: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Any]:

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
