from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


POSITION_LABELS = {
    8002: "QB",
    8003: "RB",
    8004: "WR",
    8005: "TE",
    8006: "DEF",
    8099: "K",
}


@dataclass
class HistoricalRankingResult:
    rankings: pd.DataFrame
    features: pd.DataFrame


def _parse_bid(value: object) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _trend_slope(group: pd.DataFrame) -> float:
    if len(group.index) < 2:
        return 0.0
    years = group["year"].astype(float)
    bids = group["winning_bid"].astype(float)
    year_centered = years - years.mean()
    denominator = float((year_centered**2).sum())
    if denominator == 0:
        return 0.0
    numerator = float((year_centered * (bids - bids.mean())).sum())
    return numerator / denominator


def build_historical_features(draft_results_df: pd.DataFrame, players_df: pd.DataFrame) -> pd.DataFrame:
    normalized = draft_results_df.rename(
        columns={
            "PlayerID": "player_id",
            "Year": "year",
            "PositionID": "position_id",
            "WinningBid": "winning_bid",
        }
    ).copy()
    normalized["player_id"] = pd.to_numeric(normalized["player_id"], errors="coerce")
    normalized["year"] = pd.to_numeric(normalized["year"], errors="coerce")
    normalized["position_id"] = pd.to_numeric(normalized["position_id"], errors="coerce")
    normalized["winning_bid"] = normalized["winning_bid"].apply(_parse_bid)
    normalized = normalized.dropna(subset=["player_id", "year"]).copy()
    if normalized.empty:
        return pd.DataFrame(
            columns=[
                "player_id", "player_name", "position", "appearances",
                "seasons_active", "avg_bid", "median_bid", "max_bid", "min_bid",
                "bid_std", "latest_year", "recent_3yr_avg", "recent_3yr_max",
                "trend_slope", "position_id", "position_baseline_bid",
                "consistency", "position_scarcity_boost",
            ]
        )
    normalized["player_id"] = normalized["player_id"].astype(int)
    normalized["year"] = normalized["year"].astype(int)

    players = players_df.rename(
        columns={
            "Player_ID": "player_id",
            "PlayerName": "player_name",
            "PositionID": "player_position_id",
        }
    ).copy()
    players["player_id"] = pd.to_numeric(players["player_id"], errors="coerce")
    players["player_position_id"] = pd.to_numeric(players["player_position_id"], errors="coerce")
    players = players.dropna(subset=["player_id"]).copy()
    players["player_id"] = players["player_id"].astype(int)
    players = players.sort_values(["player_id", "player_name"]).drop_duplicates("player_id", keep="first")

    grouped = normalized.groupby("player_id", as_index=False)
    features = grouped.agg(
        appearances=("player_id", "count"),
        seasons_active=("year", "nunique"),
        avg_bid=("winning_bid", "mean"),
        median_bid=("winning_bid", "median"),
        max_bid=("winning_bid", "max"),
        min_bid=("winning_bid", "min"),
        bid_std=("winning_bid", "std"),
        latest_year=("year", "max"),
    )

    recent_cutoff = int(normalized["year"].max()) - 2
    recent = normalized[normalized["year"] >= recent_cutoff]
    recent_features = (
        recent.groupby("player_id", as_index=False)
        .agg(
            recent_3yr_avg=("winning_bid", "mean"),
            recent_3yr_max=("winning_bid", "max"),
        )
    )
    features = features.merge(recent_features, on="player_id", how="left")

    trend = (
        normalized.groupby("player_id")
        .apply(_trend_slope)
        .reset_index(name="trend_slope")
    )
    features = features.merge(trend, on="player_id", how="left")

    position = (
        normalized.sort_values("year")
        .groupby("player_id", as_index=False)
        .tail(1)[["player_id", "position_id"]]
    )
    features = features.merge(position, on="player_id", how="left")
    features = features.merge(players[["player_id", "player_name", "player_position_id"]], on="player_id", how="left")

    features["position_id"] = features["position_id"].fillna(features["player_position_id"])
    features = features.drop(columns=["player_position_id"])
    features["position_id"] = features["position_id"].fillna(0).astype(int)
    features["position"] = features["position_id"].map(POSITION_LABELS).fillna("UNK")

    position_baseline = (
        features.groupby("position", as_index=False)
        .agg(position_baseline_bid=("avg_bid", "mean"))
    )
    features = features.merge(position_baseline, on="position", how="left")

    numeric_columns = [
        "avg_bid",
        "median_bid",
        "max_bid",
        "min_bid",
        "bid_std",
        "recent_3yr_avg",
        "recent_3yr_max",
        "trend_slope",
        "position_baseline_bid",
    ]
    for column in numeric_columns:
        features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0.0)

    features["bid_std"] = features["bid_std"].fillna(0.0)
    features["consistency"] = 1.0 / (1.0 + features["bid_std"])
    features["position_scarcity_boost"] = (
        (features["avg_bid"] - features["position_baseline_bid"]).clip(lower=-20, upper=20) / 20.0
    )
    return features


def score_historical_rankings(features_df: pd.DataFrame, target_season: int) -> pd.DataFrame:
    scored = features_df.copy()
    scored["model_score"] = (
        0.35 * scored["recent_3yr_avg"]
        + 0.25 * scored["avg_bid"]
        + 0.15 * scored["trend_slope"]
        + 0.10 * scored["consistency"] * 10
        + 0.15 * scored["position_scarcity_boost"] * 10
    )

    scored["predicted_auction_value"] = (
        0.55 * scored["recent_3yr_avg"]
        + 0.30 * scored["avg_bid"]
        + 0.15 * scored["max_bid"] * 0.6
    ).clip(lower=1.0)

    replacement_by_position = (
        scored.groupby("position", as_index=False)
        .agg(position_replacement=("predicted_auction_value", lambda values: values.quantile(0.35)))
    )
    scored = scored.merge(replacement_by_position, on="position", how="left")
    scored["value_over_replacement"] = (
        scored["predicted_auction_value"] - scored["position_replacement"]
    )

    scored = scored.sort_values(["model_score", "predicted_auction_value"], ascending=False).reset_index(drop=True)
    scored["rank"] = scored.index + 1
    scored["season"] = int(target_season)

    quantiles = scored["model_score"].quantile([0.80, 0.60, 0.40, 0.20]).to_dict()

    def to_tier(score: float) -> str:
        if score >= quantiles[0.80]:
            return "S"
        if score >= quantiles[0.60]:
            return "A"
        if score >= quantiles[0.40]:
            return "B"
        if score >= quantiles[0.20]:
            return "C"
        return "D"

    scored["consensus_tier"] = scored["model_score"].apply(to_tier)

    return scored[
        [
            "season",
            "rank",
            "player_id",
            "player_name",
            "position",
            "predicted_auction_value",
            "value_over_replacement",
            "model_score",
            "consensus_tier",
            "avg_bid",
            "median_bid",
            "recent_3yr_avg",
            "trend_slope",
            "appearances",
        ]
    ]


def build_rankings_from_history(
    draft_results_path: str | Path,
    players_path: str | Path,
    target_season: int,
) -> HistoricalRankingResult:
    def read_csv_with_fallback(path: str | Path) -> pd.DataFrame:
        try:
            return pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="latin-1")

    draft_results_df = read_csv_with_fallback(draft_results_path)
    players_df = read_csv_with_fallback(players_path)

    features = build_historical_features(draft_results_df, players_df)
    rankings = score_historical_rankings(features, target_season=target_season)
    return HistoricalRankingResult(rankings=rankings, features=features)


# Reverse mapping: position string stored in DB → legacy numeric PositionID
# used by build_historical_features.
_POSITION_IDS: dict[str, int] = {v: k for k, v in POSITION_LABELS.items()}
_POSITION_IDS.update({"DST": 8006, "D/ST": 8006})


def build_rankings_from_db(db: "Session", target_season: int) -> HistoricalRankingResult:
    """Build historical rankings by querying the database instead of reading CSV files.

    Produces the same result as ``build_rankings_from_history`` but sources
    draft_picks and players directly from the live DB.  Use this function once
    the CSV data files have been retired.
    """
    import backend.models as models

    picks_rows = (
        db.query(
            models.DraftPick.player_id.label("PlayerID"),
            models.DraftPick.year.label("Year"),
            models.DraftPick.amount.label("WinningBid"),
            models.Player.position.label("position_str"),
        )
        .join(models.Player, models.Player.id == models.DraftPick.player_id)
        .filter(models.DraftPick.year.isnot(None))
        .all()
    )

    draft_results_df = pd.DataFrame(
        [dict(r._mapping) for r in picks_rows],
        columns=["PlayerID", "Year", "WinningBid", "position_str"],
    )
    draft_results_df["PositionID"] = (
        draft_results_df["position_str"]
        .str.upper()
        .map(_POSITION_IDS)
        .fillna(0)
        .astype(int)
    )
    draft_results_df = draft_results_df.drop(columns=["position_str"])

    players_rows = (
        db.query(
            models.Player.id.label("Player_ID"),
            models.Player.name.label("PlayerName"),
            models.Player.position.label("position"),
        )
        .all()
    )
    players_df = pd.DataFrame(
        [dict(r._mapping) for r in players_rows],
        columns=["Player_ID", "PlayerName", "position"],
    )
    players_df["PositionID"] = (
        players_df["position"].str.upper().map(_POSITION_IDS).fillna(0).astype(int)
    )
    players_df = players_df.drop(columns=["position"])

    features = build_historical_features(draft_results_df, players_df)
    if features.empty:
        raise ValueError(
            "No historical draft picks found in the database. "
            "Run load_ppl_history.py (or the MFL import pipeline) to populate "
            "the draft_picks table before running historical rankings."
        )
    rankings = score_historical_rankings(features, target_season=target_season)
    return HistoricalRankingResult(rankings=rankings, features=features)

