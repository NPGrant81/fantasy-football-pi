"""
ML Feature Computation Module — Issue #106
==========================================
Implements offline training features for all three levels defined in
``etl/feature_registry.yml``:

  - Player-season features  (draft cost history, scarcity, bargain, volatility)
  - Owner-season features   (budget drift, vs-league-avg delta, keeper metrics)
  - Draft-season features   (inflation, budget distribution, scarcity curve,
                             replacement-level value, positional demand)

Owner-season *behavioral* features (aggressiveness_index, positional_bias_index,
spend_by_position, etc.) are computed by
``etl.transform.owner_budget_timeline.build_owner_behavior_features`` — this
module extends those results with the additional features defined in the registry.

Usage::

    from etl.transform.ml_features import (
        compute_player_draft_features,
        compute_owner_season_extensions,
        compute_draft_season_features,
    )
"""
from __future__ import annotations

import statistics
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _safe_stdev(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) >= 2 else None


def _safe_median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _gini(values: list[float]) -> float | None:
    """Gini coefficient for a list of non-negative floats."""
    if not values or len(values) < 2:
        return None
    n = len(values)
    sorted_vals = sorted(values)
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    cumulative = 0.0
    rank_sum = 0.0
    for i, v in enumerate(sorted_vals, 1):
        cumulative += v
        rank_sum += cumulative
    # Standard Gini formula
    return round(1 - (2 * rank_sum) / (n * total) + 1 / n, 6)


def _slope(xs: list[float], ys: list[float]) -> float | None:
    """Linear regression slope via least squares. Returns None if < 2 points."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den = sum((x - x_mean) ** 2 for x in xs)
    return round(num / den, 6) if den != 0 else 0.0


# ---------------------------------------------------------------------------
# Player-season draft features
# ---------------------------------------------------------------------------

def compute_player_draft_features(
    validated_draft_df: pd.DataFrame,
    *,
    reference_season: int | None = None,
) -> pd.DataFrame:
    """Compute per-player-season draft-cost features from validated draft results.

    Parameters
    ----------
    validated_draft_df:
        Output of ``validate_historical_draft_results`` — one row per pick;
        must have columns: player_id, season_year, position_id, winning_bid, is_keeper.
    reference_season:
        If supplied, features are computed using only seasons < reference_season
        (offline training context).  If None, all seasons are used (historical
        analysis context).

    Returns
    -------
    DataFrame with one row per (player_id, season_year) containing:
        player_id, season_year, draft_avg_cost, draft_max_cost, draft_median_cost,
        bidding_war_likelihood, bargain_score, positional_scarcity_index, is_keeper.

    Notes
    -----
    ``bargain_score`` is computed relative to the position average cost *within
    the same season* — there is no future leakage because both values come from
    the same completed draft.  However, this feature is still marked
    ``online: false`` in the registry because the full position average is only
    knowable after the draft completes.
    """
    required = {"player_id", "season_year", "winning_bid", "is_keeper"}
    missing = required - set(validated_draft_df.columns)
    if missing:
        raise ValueError(f"compute_player_draft_features: missing columns {sorted(missing)}")

    if validated_draft_df.empty:
        return pd.DataFrame(
            columns=[
                "player_id", "season_year", "draft_avg_cost", "draft_max_cost",
                "draft_median_cost", "bidding_war_likelihood", "bargain_score",
                "positional_scarcity_index", "is_keeper",
            ]
        )

    df = validated_draft_df.copy()
    df["player_id"] = pd.to_numeric(df["player_id"], errors="coerce")
    df["season_year"] = pd.to_numeric(df["season_year"], errors="coerce")
    df["winning_bid"] = pd.to_numeric(df["winning_bid"], errors="coerce")
    df = df.dropna(subset=["player_id", "season_year", "winning_bid"]).copy()
    df["player_id"] = df["player_id"].astype(int)
    df["season_year"] = df["season_year"].astype(int)

    # --- Position average cost per season (for bargain_score) ---
    pos_avg: dict[tuple[int, int], float] = {}  # (season_year, position_id) → avg cost
    if "position_id" in df.columns:
        pos_df = df.dropna(subset=["position_id"]).copy()
        pos_df["position_id"] = pos_df["position_id"].astype(int)
        for (yr, pos), grp in pos_df.groupby(["season_year", "position_id"]):
            bids = grp["winning_bid"].dropna().tolist()
            avg = _safe_mean(bids)
            if avg is not None:
                pos_avg[(int(yr), int(pos))] = avg

    # --- Positional pick counts per season (for scarcity index) ---
    pos_pick_count: dict[tuple[int, int], int] = {}
    total_pick_count: dict[int, int] = {}
    if "position_id" in df.columns:
        pos_df2 = df.dropna(subset=["position_id"]).copy()
        pos_df2["position_id"] = pos_df2["position_id"].astype(int)
        for yr, yr_grp in pos_df2.groupby("season_year"):
            total_pick_count[int(yr)] = len(yr_grp)
            for pos, pos_grp in yr_grp.groupby("position_id"):
                pos_pick_count[(int(yr), int(pos))] = len(pos_grp)

    # --- Historical cost lookup per player (for avg/max/median/cv) ---
    # Maps player_id → sorted list of (season_year, winning_bid)
    player_history: dict[int, list[tuple[int, float]]] = {}
    for _, row in df.iterrows():
        pid = int(row["player_id"])
        player_history.setdefault(pid, []).append((int(row["season_year"]), float(row["winning_bid"])))

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        pid = int(row["player_id"])
        season = int(row["season_year"])
        bid = float(row["winning_bid"])
        pos_id = int(row["position_id"]) if "position_id" in row and not pd.isna(row.get("position_id")) else None

        # Historical bids: all seasons < reference_season (or all if None)
        history = [
            b for (yr, b) in player_history[pid]
            if reference_season is None or yr < reference_season
        ]

        draft_avg = _safe_mean(history)
        draft_max = max(history) if history else None
        draft_median = _safe_median(history)

        # Bidding war likelihood: CV = stdev / mean (requires ≥ 2 seasons)
        cv: float | None = None
        if len(history) >= 2 and draft_avg and draft_avg > 0:
            stdev = _safe_stdev(history)
            if stdev is not None:
                cv = round(stdev / draft_avg, 6)

        # Bargain score: (pos_avg - bid) / pos_avg
        bargain: float | None = None
        if pos_id is not None:
            p_avg = pos_avg.get((season, pos_id))
            if p_avg and p_avg > 0:
                bargain = round((p_avg - bid) / p_avg, 6)

        # Positional scarcity index: picks_at_pos / total_picks
        scarcity: float | None = None
        if pos_id is not None:
            total = total_pick_count.get(season)
            pos_n = pos_pick_count.get((season, pos_id))
            if total and pos_n:
                scarcity = round(pos_n / total, 6)

        is_keeper = bool(row.get("is_keeper", False))

        rows.append({
            "player_id": pid,
            "season_year": season,
            "draft_avg_cost": round(draft_avg, 4) if draft_avg is not None else None,
            "draft_max_cost": round(draft_max, 4) if draft_max is not None else None,
            "draft_median_cost": round(draft_median, 4) if draft_median is not None else None,
            "bidding_war_likelihood": cv,
            "bargain_score": bargain,
            "positional_scarcity_index": scarcity,
            "is_keeper": is_keeper,
        })

    result = pd.DataFrame(rows).sort_values(
        ["player_id", "season_year"], kind="mergesort"
    ).reset_index(drop=True)
    return result


# ---------------------------------------------------------------------------
# Owner-season extension features
# ---------------------------------------------------------------------------

def compute_owner_season_extensions(
    behavior_df: pd.DataFrame,
) -> pd.DataFrame:
    """Extend the owner-season behavior DataFrame with additional registry features.

    Adds the following columns (defined in feature_registry.yml):
      - budget_drift: (total_spend - starting_budget) / starting_budget
      - keeper_count: populated from validated_draft_df via compute_keeper_metrics
      - keeper_spend: populated from validated_draft_df via compute_keeper_metrics
      - owner_vs_league_avg_spend: per-position delta from league average

    Call ``compute_keeper_metrics`` first and join the result, then pass here.

    Parameters
    ----------
    behavior_df:
        Output of ``build_owner_behavior_features``.  Must have columns:
        total_spend, starting_budget, position_spend_pct.

    Returns
    -------
    behavior_df with new columns appended in-place copy.
    """
    if behavior_df.empty:
        return behavior_df.copy()

    df = behavior_df.copy()

    # Budget drift
    if "total_spend" in df.columns and "starting_budget" in df.columns:
        def _drift(row: pd.Series) -> float | None:
            ts = row.get("total_spend")
            sb = row.get("starting_budget")
            if pd.isna(ts) or pd.isna(sb) or sb == 0:
                return None
            return round((float(ts) - float(sb)) / float(sb), 6)

        df["budget_drift"] = df.apply(_drift, axis=1)
    else:
        df["budget_drift"] = None

    # owner_vs_league_avg_spend: requires league-level position spend pct per season
    # Compute league avg per season from all rows in behavior_df
    if "position_spend_pct" in df.columns and "season_year" in df.columns:
        # Build league avg per season
        league_avg: dict[int, dict[str, float]] = {}
        for season, grp in df.groupby("season_year"):
            all_positions: set[str] = set()
            for pct_dict in grp["position_spend_pct"].dropna():
                if isinstance(pct_dict, dict):
                    all_positions |= pct_dict.keys()
            if not all_positions:
                continue
            pos_means: dict[str, float] = {}
            for pos in all_positions:
                vals = [
                    float(pct_dict.get(pos, 0.0))
                    for pct_dict in grp["position_spend_pct"].dropna()
                    if isinstance(pct_dict, dict)
                ]
                pos_means[pos] = round(sum(vals) / len(vals), 6) if vals else 0.0
            league_avg[int(season)] = pos_means

        def _vs_league(row: pd.Series) -> dict[str, float] | None:
            pct = row.get("position_spend_pct")
            season = row.get("season_year")
            if not isinstance(pct, dict) or season not in league_avg:
                return None
            avg = league_avg[int(season)]
            all_pos = set(pct.keys()) | set(avg.keys())
            return {
                pos: round(pct.get(pos, 0.0) - avg.get(pos, 0.0), 6)
                for pos in sorted(all_pos)
            }

        df["owner_vs_league_avg_spend"] = df.apply(_vs_league, axis=1)
    else:
        df["owner_vs_league_avg_spend"] = None

    return df


def compute_keeper_metrics(
    validated_draft_df: pd.DataFrame,
) -> pd.DataFrame:
    """Return per-owner-season keeper_count and keeper_spend.

    Parameters
    ----------
    validated_draft_df:
        Must have columns: owner_id, season_year, is_keeper, winning_bid.

    Returns
    -------
    DataFrame with columns: owner_id, season_year, keeper_count, keeper_spend.
    """
    required = {"owner_id", "season_year", "is_keeper", "winning_bid"}
    if required - set(validated_draft_df.columns) or validated_draft_df.empty:
        return pd.DataFrame(columns=["owner_id", "season_year", "keeper_count", "keeper_spend"])

    df = validated_draft_df.copy()
    df["owner_id"] = pd.to_numeric(df["owner_id"], errors="coerce")
    df["season_year"] = pd.to_numeric(df["season_year"], errors="coerce")
    df["winning_bid"] = pd.to_numeric(df["winning_bid"], errors="coerce")
    df = df.dropna(subset=["owner_id", "season_year"]).copy()
    df["owner_id"] = df["owner_id"].astype(int)
    df["season_year"] = df["season_year"].astype(int)

    keeper_df = df[df["is_keeper"] == True].copy()  # noqa: E712

    rows: list[dict[str, Any]] = []
    for (season, owner), grp in df.groupby(["season_year", "owner_id"]):
        kgrp = keeper_df[
            (keeper_df["season_year"] == season) & (keeper_df["owner_id"] == owner)
        ]
        rows.append({
            "owner_id": int(owner),
            "season_year": int(season),
            "keeper_count": int(len(kgrp)),
            "keeper_spend": round(float(kgrp["winning_bid"].sum()), 2),
        })

    return pd.DataFrame(rows).sort_values(["season_year", "owner_id"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Draft-season features
# ---------------------------------------------------------------------------

def compute_draft_season_features(
    validated_draft_df: pd.DataFrame,
    position_abbrev_map: dict[int, str] | None = None,
) -> pd.DataFrame:
    """Compute one row per season with draft-level aggregate features.

    Parameters
    ----------
    validated_draft_df:
        Must have columns: season_year, owner_id, player_id, position_id,
        winning_bid, is_keeper.
    position_abbrev_map:
        Optional {position_id: abbreviation} lookup for human-readable output.
        Falls back to string representation of position_id if not provided.

    Returns
    -------
    DataFrame with one row per season_year and columns:
        season_year, total_league_spend, avg_cost_by_position,
        league_avg_position_spend_pct, pick_count_by_position,
        positional_demand, budget_distribution_gini,
        replacement_level_value, inflation_index, scarcity_curve_slope.
    """
    required = {"season_year", "owner_id", "winning_bid", "is_keeper"}
    missing = required - set(validated_draft_df.columns)
    if missing:
        raise ValueError(f"compute_draft_season_features: missing columns {sorted(missing)}")

    if validated_draft_df.empty:
        return pd.DataFrame(
            columns=[
                "season_year", "total_league_spend", "avg_cost_by_position",
                "league_avg_position_spend_pct", "pick_count_by_position",
                "positional_demand", "budget_distribution_gini",
                "replacement_level_value", "inflation_index", "scarcity_curve_slope",
            ]
        )

    pmap = position_abbrev_map or {}

    df = validated_draft_df.copy()
    df["season_year"] = pd.to_numeric(df["season_year"], errors="coerce")
    df["owner_id"] = pd.to_numeric(df["owner_id"], errors="coerce")
    df["winning_bid"] = pd.to_numeric(df["winning_bid"], errors="coerce")
    df = df.dropna(subset=["season_year", "owner_id", "winning_bid"]).copy()
    df["season_year"] = df["season_year"].astype(int)
    df["owner_id"] = df["owner_id"].astype(int)

    has_pos = "position_id" in df.columns
    if has_pos:
        df["position_id"] = pd.to_numeric(df["position_id"], errors="coerce")
        df["pos_label"] = df["position_id"].apply(
            lambda v: pmap.get(int(v), str(int(v))) if not pd.isna(v) else "UNKNOWN"
        )

    # Store per-season avg_cost for inflation_index (needs sorted seasons)
    season_pos_avg: dict[int, dict[str, float]] = {}

    rows: list[dict[str, Any]] = []
    for season, season_df in df.groupby("season_year"):
        season = int(season)
        non_keeper = season_df[season_df["is_keeper"] != True]  # noqa: E712
        total_spend = round(float(season_df["winning_bid"].sum()), 2)
        total_non_keeper_spend = float(non_keeper["winning_bid"].sum())

        # Owner totals for Gini
        owner_totals = season_df.groupby("owner_id")["winning_bid"].sum().tolist()
        gini = _gini([float(v) for v in owner_totals])

        if has_pos:
            pos_df = season_df.dropna(subset=["pos_label"]).copy()

            # avg_cost_by_position (all picks, not just non-keeper)
            avg_cost = {
                pos: round(float(grp["winning_bid"].mean()), 4)
                for pos, grp in pos_df.groupby("pos_label")
            }

            # league_avg_position_spend_pct
            pos_spend_totals = {
                pos: float(grp["winning_bid"].sum())
                for pos, grp in pos_df.groupby("pos_label")
            }
            league_pct = {
                pos: round(spend / total_spend, 6) if total_spend > 0 else 0.0
                for pos, spend in pos_spend_totals.items()
            }

            # pick_count_by_position
            pick_count = {
                pos: int(len(grp))
                for pos, grp in pos_df.groupby("pos_label")
            }

            # positional_demand (normalized fraction)
            total_picks = sum(pick_count.values())
            pos_demand = {
                pos: round(cnt / total_picks, 6) if total_picks > 0 else 0.0
                for pos, cnt in pick_count.items()
            }

            # replacement_level_value: cheapest non-keeper pick per position
            non_keeper_pos = non_keeper.dropna(subset=["pos_label"]) if has_pos else pd.DataFrame()
            repl_level: dict[str, float] = {}
            if "pos_label" in non_keeper_pos.columns:
                for pos, grp in non_keeper_pos.groupby("pos_label"):
                    bids = grp["winning_bid"].dropna()
                    if not bids.empty:
                        repl_level[pos] = round(float(bids.min()), 4)

            # scarcity_curve_slope: bid vs pick order within position
            scarcity_slope: dict[str, float | None] = {}
            for pos, grp in pos_df.groupby("pos_label"):
                sorted_bids = sorted(grp["winning_bid"].dropna().tolist(), reverse=True)
                xs = list(range(1, len(sorted_bids) + 1))
                sl = _slope(xs, sorted_bids)
                scarcity_slope[pos] = sl

            season_pos_avg[season] = avg_cost
        else:
            avg_cost = {}
            league_pct = {}
            pick_count = {}
            pos_demand = {}
            repl_level = {}
            scarcity_slope = {}
            season_pos_avg[season] = {}

        rows.append({
            "season_year": season,
            "total_league_spend": total_spend,
            "avg_cost_by_position": avg_cost,
            "league_avg_position_spend_pct": league_pct,
            "pick_count_by_position": pick_count,
            "positional_demand": pos_demand,
            "budget_distribution_gini": gini,
            "replacement_level_value": repl_level,
            "scarcity_curve_slope": scarcity_slope,
        })

    result_df = pd.DataFrame(rows).sort_values("season_year").reset_index(drop=True)

    # --- Inflation index: requires sorted seasons to look back ---
    sorted_seasons = sorted(season_pos_avg.keys())
    inflation_rows: list[dict[str, float | None] | None] = []
    for i, season in enumerate(sorted_seasons):
        if i == 0:
            inflation_rows.append(None)
        else:
            prev_avg = season_pos_avg[sorted_seasons[i - 1]]
            curr_avg = season_pos_avg[season]
            infl: dict[str, float | None] = {}
            for pos in set(curr_avg.keys()) | set(prev_avg.keys()):
                curr = curr_avg.get(pos)
                prev = prev_avg.get(pos)
                if curr is not None and prev is not None and prev > 0:
                    infl[pos] = round(curr / prev - 1, 6)
                else:
                    infl[pos] = None
            inflation_rows.append(infl)

    result_df["inflation_index"] = inflation_rows

    return result_df
