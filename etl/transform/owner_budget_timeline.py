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


def build_owner_behavior_features(
    timeline_df: pd.DataFrame,
    draft_results_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    *,
    etl_version: str = "v1",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Compute per-owner-per-season behavioral features from the draft spend timeline.

    Parameters
    ----------
    timeline_df:
        Output of ``build_owner_budget_timeline`` — one row per draft pick event.
    draft_results_df:
        Source draft results with ``OwnerID``, ``Year``, ``WinningBid``, ``PositionID``.
    positions_df:
        Source positions table with ``PositionID`` and ``Position`` columns.
    etl_version:
        Version tag written to the ``etl_version`` column for lineage tracking.

    Returns
    -------
    (behavior_df, report_dict)
        ``behavior_df`` has one row per (season_year, owner_id) with all feature columns.
        ``report_dict`` is a JSON-serialisable summary for gate evidence.
    """
    # ------------------------------------------------------------------ #
    # 1. Build position ID → abbreviation lookup                          #
    # ------------------------------------------------------------------ #
    pos_lookup: dict[int, str] = {}
    if not positions_df.empty and "PositionID" in positions_df.columns and "Position" in positions_df.columns:
        for _, row in positions_df.iterrows():
            pid = _parse_int(row.get("PositionID"))
            abbr = str(row.get("Position", "")).strip()
            if pid is not None and abbr:
                pos_lookup[pid] = abbr

    # ------------------------------------------------------------------ #
    # 2. Enrich draft results with position abbreviation                  #
    # ------------------------------------------------------------------ #
    dr = draft_results_df.copy()
    dr["owner_id"] = pd.to_numeric(dr.get("OwnerID"), errors="coerce")
    dr["season_year"] = pd.to_numeric(dr.get("Year"), errors="coerce")
    dr["winning_bid"] = dr.get("WinningBid", pd.Series(dtype=float)).apply(_parse_dollars)
    dr["position_id_raw"] = pd.to_numeric(dr.get("PositionID"), errors="coerce")
    dr = dr.dropna(subset=["owner_id", "season_year", "winning_bid"]).copy()
    dr["owner_id"] = dr["owner_id"].astype(int)
    dr["season_year"] = dr["season_year"].astype(int)
    dr["position_id"] = dr["position_id_raw"].apply(
        lambda v: _parse_int(v) if not pd.isna(v) else None
    )
    dr["position_abbr"] = dr["position_id"].map(lambda pid: pos_lookup.get(pid, "UNKNOWN") if pid else "UNKNOWN")

    # ------------------------------------------------------------------ #
    # 3. Build owner-season budget summary from timeline_df               #
    # ------------------------------------------------------------------ #
    budget_summary: dict[tuple[int, int], dict[str, Any]] = {}
    if not timeline_df.empty:
        for (season_year, owner_id), grp in timeline_df.groupby(["season_year", "owner_id"]):
            last_row = grp.sort_values("event_sequence").iloc[-1]
            budget_summary[(int(season_year), int(owner_id))] = {
                "starting_budget": float(last_row["starting_budget"]) if not pd.isna(last_row["starting_budget"]) else None,
                "total_spend": float(last_row["cumulative_spend"]) if not pd.isna(last_row["cumulative_spend"]) else None,
                "remaining_budget": float(last_row["remaining_budget"]) if not pd.isna(last_row["remaining_budget"]) else None,
                "budget_source": str(last_row.get("budget_source", "")),
                "overspent": bool(last_row.get("overspent", False)),
            }

    # ------------------------------------------------------------------ #
    # 4. Compute league-average positional spend % per season             #
    # ------------------------------------------------------------------ #
    league_avg_pct: dict[int, dict[str, float]] = {}
    for season_year, season_grp in dr.groupby("season_year"):
        total_season_spend = float(season_grp["winning_bid"].sum())
        if total_season_spend <= 0:
            continue
        pos_totals = season_grp.groupby("position_abbr")["winning_bid"].sum()
        league_avg_pct[int(season_year)] = {
            pos: round(float(spend) / total_season_spend, 6)
            for pos, spend in pos_totals.items()
        }

    # ------------------------------------------------------------------ #
    # 5. Build per-owner-season feature rows                              #
    # ------------------------------------------------------------------ #
    feature_rows: list[dict[str, Any]] = []
    null_rate_tracker: dict[str, int] = {
        "aggressiveness_index": 0,
        "positional_bias_index": 0,
        "starting_budget": 0,
    }
    total_pairs = 0

    for (season_year, owner_id), owner_grp in dr.groupby(["season_year", "owner_id"]):
        total_pairs += 1
        season_year = int(season_year)
        owner_id = int(owner_id)

        bids = owner_grp["winning_bid"].dropna().values
        positions = owner_grp["position_abbr"].values
        total_spend = float(sum(bids)) if len(bids) > 0 else 0.0

        # Per-position breakdown
        pos_spend: dict[str, float] = {}
        pos_count: dict[str, int] = {}
        pos_max: dict[str, float] = {}
        pos_sum: dict[str, float] = {}
        for bid, pos in zip(bids, positions):
            pos_spend[pos] = pos_spend.get(pos, 0.0) + float(bid)
            pos_count[pos] = pos_count.get(pos, 0) + 1
            pos_max[pos] = max(pos_max.get(pos, 0.0), float(bid))
            pos_sum[pos] = pos_sum.get(pos, 0.0) + float(bid)

        pos_pct = {
            pos: round(spend / total_spend, 6) if total_spend > 0 else 0.0
            for pos, spend in pos_spend.items()
        }
        avg_bid = {
            pos: round(pos_sum[pos] / pos_count[pos], 4) if pos_count[pos] > 0 else 0.0
            for pos in pos_count
        }

        # Aggressiveness index: spend in top-quartile bids / total spend
        agg_index: float | None = None
        if len(bids) >= 1:
            sorted_bids = sorted(bids, reverse=True)
            top_n = max(1, len(sorted_bids) // 4)
            agg_index = round(float(sum(sorted_bids[:top_n])) / total_spend, 6) if total_spend > 0 else None
        if agg_index is None:
            null_rate_tracker["aggressiveness_index"] += 1

        # Positional bias index: mean absolute deviation from league-avg position %
        pbias: float | None = None
        league_avgs = league_avg_pct.get(season_year, {})
        if league_avgs and pos_pct:
            all_positions = set(league_avgs.keys()) | set(pos_pct.keys())
            deviations = [abs(pos_pct.get(p, 0.0) - league_avgs.get(p, 0.0)) for p in all_positions]
            pbias = round(float(sum(deviations)) / len(deviations), 6) if deviations else None
        if pbias is None:
            null_rate_tracker["positional_bias_index"] += 1

        budget_row = budget_summary.get((season_year, owner_id), {})
        if not budget_row.get("starting_budget"):
            null_rate_tracker["starting_budget"] += 1

        feature_rows.append({
            "season_year": season_year,
            "owner_id": owner_id,
            "starting_budget": budget_row.get("starting_budget"),
            "total_spend": round(total_spend, 2),
            "remaining_budget": budget_row.get("remaining_budget"),
            "budget_source": budget_row.get("budget_source"),
            "overspent": budget_row.get("overspent"),
            "spend_by_position": {k: round(v, 2) for k, v in pos_spend.items()},
            "pick_count_by_position": pos_count,
            "position_spend_pct": pos_pct,
            "max_bid_by_position": {k: round(v, 2) for k, v in pos_max.items()},
            "avg_bid_by_position": avg_bid,
            "aggressiveness_index": agg_index,
            "positional_bias_index": pbias,
            "etl_version": etl_version,
        })

    behavior_df = pd.DataFrame(feature_rows).sort_values(
        by=["season_year", "owner_id"], kind="mergesort"
    ).reset_index(drop=True) if feature_rows else pd.DataFrame()

    null_rates = {
        key: round(count / total_pairs, 4) if total_pairs > 0 else None
        for key, count in null_rate_tracker.items()
    }

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "etl_version": etl_version,
        "owner_season_pairs": total_pairs,
        "behavior_rows": len(feature_rows),
        "null_rates": null_rates,
        "league_seasons_with_position_data": len(league_avg_pct),
        "positions_seen": sorted({p for grp in league_avg_pct.values() for p in grp}),
    }

    return behavior_df, report


def write_behavior_feature_outputs_from_dataframes(
    *,
    draft_budget_df: pd.DataFrame,
    draft_results_df: pd.DataFrame,
    users_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    output_dir: Path,
    etl_version: str = "v1",
) -> dict[str, Any]:
    """Build budget timeline + behavior features and write all outputs to ``output_dir``."""
    timeline_df, _timeline_report = build_owner_budget_timeline(
        draft_budget_df, draft_results_df, users_df
    )
    behavior_df, behavior_report = build_owner_behavior_features(
        timeline_df, draft_results_df, positions_df, etl_version=etl_version
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    behavior_csv = output_dir / f"owner_behavior_features_{etl_version}.csv"
    behavior_report_path = output_dir / f"owner_behavior_report_{etl_version}.json"

    behavior_df.to_csv(behavior_csv, index=False)
    behavior_report_path.write_text(json.dumps(behavior_report, indent=2), encoding="utf-8")

    return {
        "behavior_csv": str(behavior_csv),
        "behavior_report": str(behavior_report_path),
        "rows": int(len(behavior_df)),
        "null_rates": behavior_report.get("null_rates", {}),
    }


def write_budget_timeline_outputs(
    draft_budget_csv: Path,
    draft_results_csv: Path,
    users_csv: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """DEPRECATED: Reads source DataFrames from CSV files.

    Use ``write_budget_timeline_outputs_from_dataframes()`` instead, which
    accepts DataFrames directly and is the active code path in
    ``etl/build_phase1_artifacts.py``.
    """
    import warnings
    warnings.warn(
        "write_budget_timeline_outputs() reads from CSV files and is a legacy interface. "
        "Call write_budget_timeline_outputs_from_dataframes() directly.",
        DeprecationWarning,
        stacklevel=2,
    )
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
