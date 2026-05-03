"""ML Feature Bridge — Issue #107 integration layer.

Converts compute_player_draft_features() and compute_draft_season_features()
outputs (Issue #106) into the ``historical_rankings_df`` format consumed by
``run_monte_carlo_draft_simulation()`` (Issue #107).

This module is the seam between the offline ML feature pipeline and the
Monte Carlo simulation engine so that each can evolve independently.

Typical usage::

    from etl.transform.ml_features import (
        compute_player_draft_features,
        compute_draft_season_features,
    )
    from etl.transform.ml_feature_bridge import build_simulation_rankings

    player_feats = compute_player_draft_features(draft_df, reference_season=2026)
    season_feats = compute_draft_season_features(draft_df, position_abbrev_map=POS_MAP)
    rankings = build_simulation_rankings(
        player_features=player_feats,
        draft_season_features=season_feats,
        target_season=2026,
    )
    # rankings is ready for run_monte_carlo_draft_simulation(..., historical_rankings_df=rankings)
"""
from __future__ import annotations

import math

import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum value floor so the simulation bidding model never sees zero.
_MIN_AUCTION_VALUE = 1.0

# Bargain score → model_score scaling factor.
# bargain_score is a relative fraction (-1 to +1 range typical); multiplying by
# predicted_auction_value converts it to an absolute-dollar quality signal.
_BARGAIN_TO_MODEL_SCORE_SCALE = 0.5

# CV → consistency mapping: reliability = 1 - min(CV, 1).
# A coefficient of variation of 1.0 (stdev == mean) maps to 0 consistency;
# CV above 1 is clipped so the output stays in [0, 1].
_MAX_CV_FOR_CLIPPING = 1.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_simulation_rankings(
    player_features: pd.DataFrame,
    draft_season_features: pd.DataFrame | None = None,
    target_season: int | None = None,
) -> pd.DataFrame:
    """Build a ``historical_rankings_df`` from ML feature outputs for Monte Carlo.

    Parameters
    ----------
    player_features:
        Output of ``compute_player_draft_features()``.  Required columns:
        ``player_id``, ``season_year``, ``draft_avg_cost``, ``bargain_score``,
        ``bidding_war_likelihood``.
    draft_season_features:
        Optional output of ``compute_draft_season_features()``.  When provided,
        ``inflation_index`` is used to forward-adjust ``predicted_auction_value``
        to the ``target_season`` price level.  Ignored if empty or None.
    target_season:
        The upcoming draft season to predict for (e.g. 2026).  Only rows with
        ``season_year < target_season`` from ``player_features`` are used.
        If ``None``, all rows are considered.

    Returns
    -------
    pd.DataFrame
        One row per player with columns:
        - ``player_id`` (int)
        - ``predicted_auction_value`` (float ≥ 1.0) — inflation-adjusted avg cost
        - ``model_score`` (float ≥ 0.0) — absolute bargain signal
        - ``consistency`` (float in [0, 1]) — bid stability (1 = very consistent)
        - ``season`` (int | None) — source season for provenance

    Raises
    ------
    ValueError
        If ``player_features`` is missing required columns.
    """
    required = {"player_id", "season_year", "draft_avg_cost", "bargain_score", "bidding_war_likelihood"}
    missing = required - set(player_features.columns)
    if missing:
        raise ValueError(f"build_simulation_rankings: player_features missing columns {sorted(missing)}")

    if player_features.empty:
        return _empty_rankings()

    df = player_features.copy()
    df["season_year"] = pd.to_numeric(df["season_year"], errors="coerce")
    df["player_id"] = pd.to_numeric(df["player_id"], errors="coerce")
    df = df.dropna(subset=["player_id", "season_year"]).copy()
    df["player_id"] = df["player_id"].astype(int)
    df["season_year"] = df["season_year"].astype(int)

    # Filter to prior seasons only.
    if target_season is not None:
        df = df[df["season_year"] < target_season].copy()

    if df.empty:
        return _empty_rankings()

    # Use each player's most recent prior season for maximum relevance.
    df = (
        df.sort_values("season_year")
        .groupby("player_id", as_index=False)
        .last()
    )

    # --- predicted_auction_value ---
    df["predicted_auction_value"] = (
        pd.to_numeric(df["draft_avg_cost"], errors="coerce")
        .fillna(_MIN_AUCTION_VALUE)
        .clip(lower=_MIN_AUCTION_VALUE)
    )

    # --- inflation adjustment ---
    inflation_map = _extract_inflation_map(draft_season_features, target_season)
    if inflation_map:
        df["predicted_auction_value"] = df.apply(
            lambda row: _apply_inflation(row["predicted_auction_value"], inflation_map),
            axis=1,
        )

    # --- model_score: absolute bargain signal ---
    # A positive bargain_score means the player was acquired below position average.
    # Scale to dollars so it can add to the base value signal.
    df["bargain_score_num"] = pd.to_numeric(df["bargain_score"], errors="coerce").fillna(0.0)
    df["model_score"] = (
        (df["bargain_score_num"].clip(lower=0.0) * df["predicted_auction_value"] * _BARGAIN_TO_MODEL_SCORE_SCALE)
        .round(4)
    )

    # --- consistency: bid stability signal (inverted CV) ---
    df["cv_num"] = pd.to_numeric(df["bidding_war_likelihood"], errors="coerce")
    df["consistency"] = df["cv_num"].apply(_cv_to_consistency)

    # --- source season for provenance ---
    df["season"] = df["season_year"].astype(int)

    return df[["player_id", "predicted_auction_value", "model_score", "consistency", "season"]].copy()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _empty_rankings() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["player_id", "predicted_auction_value", "model_score", "consistency", "season"]
    )


def _cv_to_consistency(cv: float | None) -> float:
    """Convert coefficient of variation to a [0, 1] consistency score.

    High CV (volatile bidding history) → low consistency.
    None/NaN → 0.5 (unknown stability → neutral).
    """
    if cv is None or (isinstance(cv, float) and math.isnan(cv)):
        return 0.5
    clipped = min(float(cv), _MAX_CV_FOR_CLIPPING)
    return round(1.0 - clipped, 6)


def _extract_inflation_map(
    draft_season_features: pd.DataFrame | None,
    target_season: int | None,
) -> dict[str, float]:
    """Build a position → inflation_rate map from draft_season_features.

    Uses the most recent season's inflation_index relative to the season
    immediately preceding ``target_season``.  Returns empty dict if data
    is unavailable or inapplicable.
    """
    if draft_season_features is None or draft_season_features.empty:
        return {}
    if target_season is None:
        return {}
    if "inflation_index" not in draft_season_features.columns:
        return {}

    dsf = draft_season_features.copy()
    dsf["season_year"] = pd.to_numeric(dsf["season_year"], errors="coerce")
    # Use the latest season before target_season that has inflation data.
    prior = dsf[(dsf["season_year"] < target_season) & dsf["inflation_index"].notna()]
    if prior.empty:
        return {}

    latest_row = prior.sort_values("season_year").iloc[-1]
    infl = latest_row["inflation_index"]
    if not isinstance(infl, dict):
        return {}

    return {pos: float(rate) for pos, rate in infl.items() if isinstance(rate, (int, float))}


def _apply_inflation(value: float, inflation_map: dict[str, float]) -> float:
    """Apply the mean inflation rate across all positions to a single value.

    Position-specific inflation is averaged because individual player positions
    are not known in the bridge (they come from the players_df in the simulation).
    This gives a first-order price-level adjustment.
    """
    if not inflation_map:
        return value
    mean_rate = sum(inflation_map.values()) / len(inflation_map)
    adjusted = value * (1.0 + mean_rate)
    return max(_MIN_AUCTION_VALUE, round(adjusted, 4))
