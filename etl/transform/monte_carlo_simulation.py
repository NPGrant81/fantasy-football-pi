from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, TYPE_CHECKING
import math
import random

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


DEFAULT_POSITION_LIMITS = {
    "QB": 2,
    "RB": 5,
    "WR": 5,
    "TE": 2,
    "DEF": 1,
    "K": 1,
}


@dataclass
class SimulationConfig:
    iterations: int = 1000
    seed: int = 42
    target_owner_id: int = 1
    teams_count: int = 12
    roster_size: int = 16
    min_bid: int = 1
    nomination_pool_size: int = 20
    budget_fallback: float = 200.0
    strategy_aggressiveness: float = 0.12
    owner_position_noise: float = 0.08
    owner_player_repeat_bonus: float = 0.10
    target_key_players: int = 15
    position_limits: dict[str, int] | None = None
    focal_owner_id: int | None = None
    focal_aggressiveness_multiplier: float = 1.0
    focal_position_weights: dict[str, float] | None = None
    focal_risk_tolerance: float = 0.5
    focal_player_reliability_weight: float = 1.0

    def resolved_position_limits(self) -> dict[str, int]:
        if self.position_limits:
            return dict(self.position_limits)
        return dict(DEFAULT_POSITION_LIMITS)

    def resolved_focal_owner_id(self) -> int:
        return int(self.focal_owner_id or self.target_owner_id)

    def resolved_focal_position_weights(self) -> dict[str, float]:
        if not self.focal_position_weights:
            return {}
        resolved: dict[str, float] = {}
        for position, weight in self.focal_position_weights.items():
            normalized_position = _normalize_position(position)
            if normalized_position == "UNK":
                continue
            try:
                numeric_weight = float(weight)
            except (TypeError, ValueError):
                continue
            resolved[normalized_position] = max(0.5, min(2.0, numeric_weight))
        return resolved


@dataclass
class MonteCarloSimulationResult:
    draft_picks: pd.DataFrame
    team_metrics: pd.DataFrame
    owner_summary: pd.DataFrame
    assumptions: dict[str, object]


def _parse_money(value: object, fallback: float = 0.0) -> float:
    if value is None:
        return fallback
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text:
        return fallback
    try:
        return float(text)
    except ValueError:
        return fallback


def _normalize_position(value: object) -> str:
    if value is None:
        return "UNK"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return "UNK"
        return POSITION_LABELS.get(int(value), "UNK")
    text = str(value).strip().upper()
    if text in {"D/ST", "DST", "DEF"}:
        return "DEF"
    if text in {"PK", "KICKER", "K"}:
        return "K"
    if text in {"QB", "RB", "WR", "TE", "DEF"}:
        return text
    return "UNK"


def _prepare_owners(draft_results_df: pd.DataFrame, budget_df: pd.DataFrame, config: SimulationConfig) -> pd.DataFrame:
    owner_spend = draft_results_df.groupby("owner_id", as_index=False).agg(
        historical_spend=("winning_bid", "mean"),
        draft_count=("player_id", "count"),
    )

    if budget_df.empty:
        budget_lookup = pd.DataFrame(
            {"owner_id": sorted(draft_results_df["owner_id"].dropna().unique()), "budget": config.budget_fallback}
        )
    else:
        budget_copy = budget_df.copy()
        budget_copy["owner_id"] = pd.to_numeric(budget_copy["OwnerID"], errors="coerce")
        budget_copy["budget"] = budget_copy["DraftBudget"].apply(
            lambda value: _parse_money(value, fallback=config.budget_fallback)
        )
        budget_lookup = (
            budget_copy.dropna(subset=["owner_id"])
            .assign(owner_id=lambda frame: frame["owner_id"].astype(int))
            .groupby("owner_id", as_index=False)["budget"]
            .max()
        )

    owners = budget_lookup.merge(owner_spend, on="owner_id", how="left")
    owners["historical_spend"] = owners["historical_spend"].fillna(config.budget_fallback / config.roster_size)
    owners["draft_count"] = owners["draft_count"].fillna(0)

    if len(owners.index) < config.teams_count:
        existing_ids = set(owners["owner_id"].tolist())
        next_id = 1
        injected = []
        while len(existing_ids) + len(injected) < config.teams_count:
            if next_id not in existing_ids:
                injected.append(
                    {
                        "owner_id": next_id,
                        "budget": config.budget_fallback,
                        "historical_spend": config.budget_fallback / config.roster_size,
                        "draft_count": 0,
                    }
                )
            next_id += 1
        if injected:
            owners = pd.concat([owners, pd.DataFrame(injected)], ignore_index=True)

    owners = owners.sort_values("owner_id").head(config.teams_count).reset_index(drop=True)
    return owners


def _prepare_players(
    players_df: pd.DataFrame,
    historical_rankings_df: pd.DataFrame,
    yearly_results_df: pd.DataFrame,
    config: SimulationConfig,
) -> pd.DataFrame:
    players = players_df.rename(
        columns={"Player_ID": "player_id", "PlayerName": "player_name", "PositionID": "position_id"}
    ).copy()
    players["player_id"] = pd.to_numeric(players["player_id"], errors="coerce")
    players = players.dropna(subset=["player_id"]).copy()
    players["player_id"] = players["player_id"].astype(int)
    players["position"] = players["position_id"].apply(_normalize_position)

    rankings = historical_rankings_df.copy()
    if rankings.empty:
        rankings = pd.DataFrame(columns=["player_id", "predicted_auction_value", "model_score", "position"])
    rankings["player_id"] = pd.to_numeric(rankings.get("player_id"), errors="coerce")
    rankings = rankings.dropna(subset=["player_id"]).copy()
    rankings["player_id"] = rankings["player_id"].astype(int)
    rankings["predicted_auction_value"] = pd.to_numeric(
        rankings.get("predicted_auction_value"), errors="coerce"
    ).fillna(1.0)
    rankings["model_score"] = pd.to_numeric(rankings.get("model_score"), errors="coerce").fillna(0.0)
    if "appearances" in rankings.columns:
        rankings["player_reliability_score"] = pd.to_numeric(
            rankings.get("appearances"), errors="coerce"
        ).fillna(0.0).clip(lower=0.0, upper=6.0) / 6.0
    elif "consistency" in rankings.columns:
        rankings["player_reliability_score"] = pd.to_numeric(
            rankings.get("consistency"), errors="coerce"
        ).fillna(0.5).clip(lower=0.0, upper=1.0)
    else:
        rankings["player_reliability_score"] = 0.5

    players = players.sort_values(["player_id", "player_name"]).drop_duplicates("player_id", keep="first")
    joined = players.merge(
        rankings[["player_id", "predicted_auction_value", "model_score", "position", "player_reliability_score"]],
        on="player_id",
        how="left",
        suffixes=("", "_rank"),
    )

    joined["position"] = joined["position_rank"].fillna(joined["position"]).apply(_normalize_position)
    joined = joined.drop(columns=["position_rank"], errors="ignore")
    joined["predicted_auction_value"] = joined["predicted_auction_value"].fillna(1.0)
    joined["model_score"] = joined["model_score"].fillna(0.0)
    joined["player_reliability_score"] = pd.to_numeric(
        joined.get("player_reliability_score"), errors="coerce"
    ).fillna(0.5).clip(lower=0.0, upper=1.0)

    if yearly_results_df.empty:
        joined["projected_points"] = (
            joined["predicted_auction_value"] * 3.2 + joined["model_score"] * 0.8
        ).clip(lower=1.0)
        joined["yearly_points_source"] = "derived_from_historical_rankings"
    else:
        yearly = yearly_results_df.copy()
        yearly.columns = [str(column) for column in yearly.columns]
        yearly_player_col = None
        yearly_points_col = None
        for candidate in ["player_id", "PlayerID", "Player_ID"]:
            if candidate in yearly.columns:
                yearly_player_col = candidate
                break
        for candidate in ["points", "Points", "ProjectedPoints", "projected_points", "FantasyPoints"]:
            if candidate in yearly.columns:
                yearly_points_col = candidate
                break

        if yearly_player_col and yearly_points_col:
            yearly["player_id"] = pd.to_numeric(yearly[yearly_player_col], errors="coerce")
            yearly["points"] = pd.to_numeric(yearly[yearly_points_col], errors="coerce")
            yearly = yearly.dropna(subset=["player_id", "points"]).copy()
            yearly["player_id"] = yearly["player_id"].astype(int)
            yearly_points = yearly.groupby("player_id", as_index=False).agg(projected_points=("points", "mean"))
            joined = joined.merge(yearly_points, on="player_id", how="left")
            joined["projected_points"] = joined["projected_points"].fillna(
                joined["predicted_auction_value"] * 3.2 + joined["model_score"] * 0.8
            )
            joined["yearly_points_source"] = "yearly_results_or_derived"
        else:
            joined["projected_points"] = (
                joined["predicted_auction_value"] * 3.2 + joined["model_score"] * 0.8
            ).clip(lower=1.0)
            joined["yearly_points_source"] = "derived_from_historical_rankings"

    joined = joined[joined["position"] != "UNK"].copy()
    joined["desirability"] = (
        joined["predicted_auction_value"] * 0.7 + joined["model_score"] * 0.3
    ).clip(lower=0.1)
    joined = joined.sort_values(["desirability", "projected_points"], ascending=False).reset_index(drop=True)
    return joined


def _owner_position_affinity(draft_results_df: pd.DataFrame) -> pd.DataFrame:
    grouped = draft_results_df.groupby(["owner_id", "position"], as_index=False).agg(
        spend=("winning_bid", "sum"),
        picks=("player_id", "count"),
    )
    totals = grouped.groupby("owner_id", as_index=False).agg(total_spend=("spend", "sum"), total_picks=("picks", "sum"))
    merged = grouped.merge(totals, on="owner_id", how="left")
    merged["spend_share"] = merged["spend"] / merged["total_spend"].replace(0, 1)
    merged["pick_share"] = merged["picks"] / merged["total_picks"].replace(0, 1)
    merged["affinity"] = (merged["spend_share"] * 0.7 + merged["pick_share"] * 0.3).fillna(0.0)
    return merged[["owner_id", "position", "affinity"]]


def _owner_player_repeats(draft_results_df: pd.DataFrame) -> pd.DataFrame:
    repeats = draft_results_df.groupby(["owner_id", "player_id"], as_index=False).agg(times=("year", "nunique"))
    repeats["repeat_bonus"] = ((repeats["times"] - 1).clip(lower=0) * 0.05).clip(upper=0.25)
    return repeats[["owner_id", "player_id", "repeat_bonus"]]


def _remaining_position_need(
    roster_counts: dict[str, int],
    limits: dict[str, int],
    roster_size: int,
    current_size: int,
    position: str,
) -> float:
    position_cap = limits.get(position, 0)
    position_remaining = max(position_cap - roster_counts.get(position, 0), 0)
    spots_remaining = max(roster_size - current_size, 0)
    if spots_remaining == 0:
        return 0.0
    need_ratio = position_remaining / spots_remaining
    return min(max(need_ratio, 0.0), 1.0)


def _eligible_for_position(roster_counts: dict[str, int], limits: dict[str, int], position: str) -> bool:
    return roster_counts.get(position, 0) < limits.get(position, 0)


def _max_affordable_bid(owner_state: dict[str, object], roster_size: int, min_bid: int) -> float:
    roster_count = int(owner_state["roster_count"])
    remaining_slots_after_this_pick = max(roster_size - roster_count - 1, 0)
    reserved_minimum = remaining_slots_after_this_pick * min_bid
    max_affordable = float(owner_state["budget_remaining"]) - float(reserved_minimum)
    return max(float(min_bid), max_affordable)


def _owner_bid_value(
    *,
    rng: random.Random,
    base_value: float,
    projected_points: float,
    position_need: float,
    position_affinity: float,
    repeat_bonus: float,
    aggressiveness: float,
    position_weight: float,
    reliability_score: float,
    reliability_weight: float,
    volatility_scale: float,
    max_budget: float,
    min_bid: int,
) -> float:
    volatility_band = 0.12 * max(0.3, volatility_scale)
    volatility = rng.uniform(-volatility_band, volatility_band)
    points_scale = math.log(max(projected_points, 1.0), 10)
    reliability_multiplier = 1.0 + (max(0.0, min(reliability_score, 1.0)) - 0.5) * (reliability_weight - 1.0)
    value = base_value
    value *= 1.0 + aggressiveness
    value *= max(0.5, position_weight)
    value *= 1.0 + position_need * 0.40
    value *= 1.0 + position_affinity * 0.35
    value *= 1.0 + repeat_bonus
    value *= max(0.5, reliability_multiplier)
    value *= 1.0 + volatility
    value += points_scale
    return float(min(max(value, float(min_bid)), max_budget))


def _run_single_iteration(
    *,
    iteration_index: int,
    rng: random.Random,
    owners_df: pd.DataFrame,
    players_df: pd.DataFrame,
    affinity_df: pd.DataFrame,
    repeats_df: pd.DataFrame,
    config: SimulationConfig,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    limits = config.resolved_position_limits()
    focal_owner_id = config.resolved_focal_owner_id()
    focal_position_weights = config.resolved_focal_position_weights()
    focal_risk_tolerance = max(0.0, min(1.0, float(config.focal_risk_tolerance)))
    focal_aggressiveness_multiplier = max(0.5, min(2.5, float(config.focal_aggressiveness_multiplier)))
    focal_reliability_weight = max(0.5, min(2.0, float(config.focal_player_reliability_weight)))

    owners_state: dict[int, dict[str, object]] = {}
    for row in owners_df.itertuples(index=False):
        owner_id = int(row.owner_id)
        owners_state[owner_id] = {
            "budget_remaining": float(row.budget),
            "roster_count": 0,
            "position_counts": {position: 0 for position in limits},
            "spend_by_position": {position: 0.0 for position in limits},
            "projected_points": 0.0,
            "value_captured": 0.0,
            "players": [],
        }

    affinity_lookup = {
        (int(row.owner_id), str(row.position)): float(row.affinity)
        for row in affinity_df.itertuples(index=False)
    }
    repeat_lookup = {
        (int(row.owner_id), int(row.player_id)): float(row.repeat_bonus)
        for row in repeats_df.itertuples(index=False)
    }

    available_players = players_df.copy()
    nomination_order = owners_df["owner_id"].astype(int).tolist()
    rng.shuffle(nomination_order)

    draft_picks: list[dict[str, object]] = []
    pick_number = 0

    while not available_players.empty:
        if all(state["roster_count"] >= config.roster_size for state in owners_state.values()):
            break

        for nominator_owner_id in nomination_order:
            if available_players.empty:
                break

            if all(state["roster_count"] >= config.roster_size for state in owners_state.values()):
                break

            needed_positions = set()
            for owner_state in owners_state.values():
                if owner_state["roster_count"] >= config.roster_size:
                    continue
                for position_name, position_cap in limits.items():
                    if owner_state["position_counts"].get(position_name, 0) < position_cap:
                        needed_positions.add(position_name)

            if not needed_positions:
                break

            eligible_pool = available_players[available_players["position"].isin(needed_positions)]
            candidate_pool = eligible_pool.head(config.nomination_pool_size)
            if candidate_pool.empty:
                break

            candidate_row = candidate_pool.sample(n=1, random_state=rng.randint(1, 1_000_000)).iloc[0]
            player_id = int(candidate_row["player_id"])
            position = str(candidate_row["position"])

            bids: list[tuple[int, float]] = []
            for owner_id, owner_state in owners_state.items():
                if owner_state["roster_count"] >= config.roster_size:
                    continue
                max_owner_bid = _max_affordable_bid(owner_state, config.roster_size, config.min_bid)
                if max_owner_bid < config.min_bid:
                    continue
                if not _eligible_for_position(owner_state["position_counts"], limits, position):
                    continue

                need_score = _remaining_position_need(
                    owner_state["position_counts"],
                    limits,
                    config.roster_size,
                    int(owner_state["roster_count"]),
                    position,
                )
                position_affinity = affinity_lookup.get((owner_id, position), 0.0)
                repeat_bonus = repeat_lookup.get((owner_id, player_id), 0.0)
                owner_aggressiveness = config.strategy_aggressiveness
                position_weight = 1.0
                volatility_scale = 1.0
                reliability_weight = 1.0
                if owner_id == focal_owner_id:
                    owner_aggressiveness *= focal_aggressiveness_multiplier
                    position_weight = focal_position_weights.get(position, 1.0)
                    volatility_scale = 0.6 + focal_risk_tolerance
                    reliability_weight = focal_reliability_weight

                owner_bid = _owner_bid_value(
                    rng=rng,
                    base_value=float(candidate_row["predicted_auction_value"]),
                    projected_points=float(candidate_row["projected_points"]),
                    position_need=need_score,
                    position_affinity=position_affinity,
                    repeat_bonus=repeat_bonus * (1.0 + config.owner_player_repeat_bonus),
                    aggressiveness=owner_aggressiveness,
                    position_weight=position_weight,
                    reliability_score=float(candidate_row.get("player_reliability_score", 0.5)),
                    reliability_weight=reliability_weight,
                    volatility_scale=volatility_scale,
                    max_budget=max_owner_bid,
                    min_bid=config.min_bid,
                )
                bids.append((owner_id, owner_bid))

            if not bids:
                available_players = available_players[available_players["player_id"] != player_id]
                continue

            bids.sort(key=lambda item: item[1], reverse=True)
            top_bid = bids[0][1]
            tied = [item for item in bids if abs(item[1] - top_bid) < 1e-9]
            if len(tied) > 1:
                winning_owner_id = rng.choice([item[0] for item in tied])
            else:
                winning_owner_id = bids[0][0]

            paid = max(config.min_bid, int(round(top_bid)))
            owner_state = owners_state[winning_owner_id]
            paid = min(paid, int(_max_affordable_bid(owner_state, config.roster_size, config.min_bid)))
            if paid < config.min_bid:
                available_players = available_players[available_players["player_id"] != player_id]
                continue

            owner_state["budget_remaining"] = float(owner_state["budget_remaining"] - paid)
            owner_state["roster_count"] = int(owner_state["roster_count"]) + 1
            owner_state["position_counts"][position] = owner_state["position_counts"].get(position, 0) + 1
            owner_state["spend_by_position"][position] = owner_state["spend_by_position"].get(position, 0.0) + paid
            owner_state["projected_points"] += float(candidate_row["projected_points"])
            owner_state["value_captured"] += float(candidate_row["predicted_auction_value"]) - paid
            owner_state["players"].append(player_id)

            pick_number += 1
            draft_picks.append(
                {
                    "iteration": iteration_index,
                    "pick_no": pick_number,
                    "nominated_by_owner_id": int(nominator_owner_id),
                    "owner_id": int(winning_owner_id),
                    "player_id": player_id,
                    "player_name": str(candidate_row["player_name"]),
                    "position": position,
                    "price_paid": float(paid),
                    "predicted_auction_value": float(candidate_row["predicted_auction_value"]),
                    "projected_points": float(candidate_row["projected_points"]),
                }
            )

            available_players = available_players[available_players["player_id"] != player_id]

    team_metrics: list[dict[str, object]] = []
    for owner_id, owner_state in owners_state.items():
        team_metrics.append(
            {
                "iteration": iteration_index,
                "owner_id": int(owner_id),
                "roster_size": int(owner_state["roster_count"]),
                "budget_remaining": float(owner_state["budget_remaining"]),
                "total_spend": float(owners_df.loc[owners_df["owner_id"] == owner_id, "budget"].iloc[0])
                - float(owner_state["budget_remaining"]),
                "projected_points": float(owner_state["projected_points"]),
                "value_captured": float(owner_state["value_captured"]),
                "spend_qb": float(owner_state["spend_by_position"].get("QB", 0.0)),
                "spend_rb": float(owner_state["spend_by_position"].get("RB", 0.0)),
                "spend_wr": float(owner_state["spend_by_position"].get("WR", 0.0)),
                "spend_te": float(owner_state["spend_by_position"].get("TE", 0.0)),
                "spend_def": float(owner_state["spend_by_position"].get("DEF", 0.0)),
                "spend_k": float(owner_state["spend_by_position"].get("K", 0.0)),
            }
        )

    return draft_picks, team_metrics


def run_monte_carlo_draft_simulation(
    *,
    draft_results_df: pd.DataFrame,
    players_df: pd.DataFrame,
    historical_rankings_df: pd.DataFrame,
    budget_df: pd.DataFrame | None = None,
    yearly_results_df: pd.DataFrame | None = None,
    config: SimulationConfig | None = None,
) -> MonteCarloSimulationResult:
    cfg = config or SimulationConfig()
    budget_df = budget_df if budget_df is not None else pd.DataFrame()
    yearly_results_df = yearly_results_df if yearly_results_df is not None else pd.DataFrame()

    normalized_draft_results = draft_results_df.rename(
        columns={"OwnerID": "owner_id", "PlayerID": "player_id", "PositionID": "position_id", "WinningBid": "winning_bid", "Year": "year"}
    ).copy()
    normalized_draft_results["owner_id"] = pd.to_numeric(normalized_draft_results["owner_id"], errors="coerce")
    normalized_draft_results["player_id"] = pd.to_numeric(normalized_draft_results["player_id"], errors="coerce")
    normalized_draft_results["position"] = normalized_draft_results["position_id"].apply(_normalize_position)
    normalized_draft_results["winning_bid"] = normalized_draft_results["winning_bid"].apply(_parse_money)
    normalized_draft_results = normalized_draft_results.dropna(subset=["owner_id", "player_id"]).copy()
    normalized_draft_results["owner_id"] = normalized_draft_results["owner_id"].astype(int)
    normalized_draft_results["player_id"] = normalized_draft_results["player_id"].astype(int)

    owners = _prepare_owners(normalized_draft_results, budget_df, cfg)
    players = _prepare_players(players_df, historical_rankings_df, yearly_results_df, cfg)
    affinities = _owner_position_affinity(normalized_draft_results)
    repeats = _owner_player_repeats(normalized_draft_results)

    rng = random.Random(cfg.seed)

    all_picks: list[dict[str, object]] = []
    all_team_metrics: list[dict[str, object]] = []
    for iteration_index in range(1, cfg.iterations + 1):
        iteration_seed = rng.randint(1, 10_000_000)
        iteration_rng = random.Random(iteration_seed)
        picks, metrics = _run_single_iteration(
            iteration_index=iteration_index,
            rng=iteration_rng,
            owners_df=owners,
            players_df=players,
            affinity_df=affinities,
            repeats_df=repeats,
            config=cfg,
        )
        all_picks.extend(picks)
        all_team_metrics.extend(metrics)

    draft_picks_df = pd.DataFrame(all_picks)
    team_metrics_df = pd.DataFrame(all_team_metrics)

    if team_metrics_df.empty:
        owner_summary_df = pd.DataFrame()
    else:
        target_owner_metrics = team_metrics_df[team_metrics_df["owner_id"] == cfg.target_owner_id].copy()

        top_targets = players.head(cfg.target_key_players)[["player_id", "player_name"]]
        target_picks = draft_picks_df[draft_picks_df["owner_id"] == cfg.target_owner_id]
        key_target_probability = top_targets.merge(
            target_picks.groupby("player_id", as_index=False).agg(hit_count=("iteration", "nunique")),
            on="player_id",
            how="left",
        )
        key_target_probability["hit_count"] = key_target_probability["hit_count"].fillna(0)
        key_target_probability["probability"] = key_target_probability["hit_count"] / max(cfg.iterations, 1)

        owner_summary_df = pd.DataFrame(
            [
                {
                    "owner_id": cfg.target_owner_id,
                    "iterations": cfg.iterations,
                    "expected_total_points": float(target_owner_metrics["projected_points"].mean()),
                    "points_stddev": float(target_owner_metrics["projected_points"].std(ddof=0)),
                    "expected_total_spend": float(target_owner_metrics["total_spend"].mean()),
                    "expected_spend_qb": float(target_owner_metrics["spend_qb"].mean()),
                    "expected_spend_rb": float(target_owner_metrics["spend_rb"].mean()),
                    "expected_spend_wr": float(target_owner_metrics["spend_wr"].mean()),
                    "expected_spend_te": float(target_owner_metrics["spend_te"].mean()),
                    "expected_spend_def": float(target_owner_metrics["spend_def"].mean()),
                    "expected_spend_k": float(target_owner_metrics["spend_k"].mean()),
                    "expected_value_captured": float(target_owner_metrics["value_captured"].mean()),
                }
            ]
        )

        if not key_target_probability.empty:
            probability_records = key_target_probability.sort_values("probability", ascending=False).head(10)
            owner_summary_df["key_target_probability_snapshot"] = "; ".join(
                f"{row.player_name}:{row.probability:.3f}" for row in probability_records.itertuples(index=False)
            )

    assumptions = {
        "league_rules": {
            "teams_count": cfg.teams_count,
            "roster_size": cfg.roster_size,
            "position_limits": cfg.resolved_position_limits(),
            "min_bid": cfg.min_bid,
        },
        "bidding_logic": {
            "base_value": "predicted_auction_value from historical_rankings",
            "owner_features": "owner position affinity + repeated-player tendencies from draft_results",
            "player_features": "projected points + model score + predicted auction value",
            "randomness": "uniform perturbation per owner bid",
        },
        "focal_owner_overrides": {
            "focal_owner_id": cfg.resolved_focal_owner_id(),
            "aggressiveness_multiplier": cfg.focal_aggressiveness_multiplier,
            "position_weights": cfg.resolved_focal_position_weights(),
            "risk_tolerance": cfg.focal_risk_tolerance,
            "player_reliability_weight": cfg.focal_player_reliability_weight,
        },
        "nomination_logic": "shuffled round-robin owner order each iteration",
        "tie_breaking": "random among top bids with equal value",
        "stopping_rules": "all teams filled to roster_size or player pool exhausted",
        "projected_points_handling": (
            "derives projected points from historical rankings when direct point inputs are unavailable"
        ),
    }

    return MonteCarloSimulationResult(
        draft_picks=draft_picks_df,
        team_metrics=team_metrics_df,
        owner_summary=owner_summary_df,
        assumptions=assumptions,
    )


# Reverse mapping: position string stored in DB → legacy numeric PositionID
_POSITION_IDS: dict[str, int] = {v: k for k, v in POSITION_LABELS.items()}
_POSITION_IDS.update({"DST": 8006, "D/ST": 8006})


def run_monte_carlo_from_db(
    db: "Session",
    *,
    league_id: int | None = None,
    config: SimulationConfig | None = None,
) -> MonteCarloSimulationResult:
    """Run Monte Carlo simulation using live database data instead of CSV files.

    Queries ``draft_picks``, ``players``, ``draft_values`` (historical rankings),
    and ``draft_budgets`` tables and passes the resulting DataFrames to the
    core simulation engine.  Use this function once the CSV data files have
    been retired.

    Parameters
    ----------
    db:
        An active SQLAlchemy Session (caller is responsible for closing it).
    league_id:
        Optional league filter.  When supplied, only draft picks belonging to
        that league are included.
    config:
        Simulation configuration.  Defaults to ``SimulationConfig()``.
    """
    from backend import models
    from backend.models_draft_value import DraftValue

    picks_query = (
        db.query(
            models.DraftPick.player_id.label("PlayerID"),
            models.DraftPick.owner_id.label("OwnerID"),
            models.DraftPick.year.label("Year"),
            models.DraftPick.amount.label("WinningBid"),
            models.Player.position.label("position_str"),
        )
        .join(models.Player, models.Player.id == models.DraftPick.player_id)
        .filter(models.DraftPick.year.isnot(None))
    )
    if league_id is not None:
        picks_query = picks_query.filter(models.DraftPick.league_id == league_id)
    picks_rows = picks_query.all()

    draft_results_df = pd.DataFrame(
        [dict(r._mapping) for r in picks_rows],
        columns=["PlayerID", "OwnerID", "Year", "WinningBid", "position_str"],
    )
    draft_results_df["PositionID"] = (
        draft_results_df["position_str"].str.upper().map(_POSITION_IDS).fillna(0).astype(int)
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

    # Load historical rankings from DraftValue table (written by build_historical_rankings --load-db).
    rankings_rows = (
        db.query(
            DraftValue.player_id.label("player_id"),
            DraftValue.avg_auction_value.label("predicted_auction_value"),
            DraftValue.median_adp.label("median_bid"),
            DraftValue.consensus_tier.label("consensus_tier"),
            DraftValue.value_over_replacement.label("value_over_replacement"),
        )
        .order_by(DraftValue.season.desc())
        .all()
    )
    historical_rankings_df = (
        pd.DataFrame([dict(r._mapping) for r in rankings_rows])
        if rankings_rows
        else pd.DataFrame()
    )

    # Load per-season draft budgets.
    budget_query = db.query(
        models.DraftBudget.owner_id.label("OwnerID"),
        models.DraftBudget.total_budget.label("DraftBudget"),
        models.DraftBudget.year.label("Year"),
    )
    if league_id is not None:
        budget_query = budget_query.filter(models.DraftBudget.league_id == league_id)
    budget_rows = budget_query.all()
    budget_df = (
        pd.DataFrame([dict(r._mapping) for r in budget_rows])
        if budget_rows
        else pd.DataFrame()
    )

    return run_monte_carlo_draft_simulation(
        draft_results_df=draft_results_df,
        players_df=players_df,
        historical_rankings_df=historical_rankings_df,
        budget_df=budget_df,
        yearly_results_df=pd.DataFrame(),
        config=config,
    )



def summarize_team_distribution(team_metrics_df: pd.DataFrame, owner_id: int) -> dict[str, float]:
    owner_metrics = team_metrics_df[team_metrics_df["owner_id"] == owner_id]
    if owner_metrics.empty:
        return {}
    quantiles = owner_metrics["projected_points"].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).to_dict()
    return {
        "points_p10": float(quantiles.get(0.1, 0.0)),
        "points_p25": float(quantiles.get(0.25, 0.0)),
        "points_p50": float(quantiles.get(0.5, 0.0)),
        "points_p75": float(quantiles.get(0.75, 0.0)),
        "points_p90": float(quantiles.get(0.9, 0.0)),
    }


def key_target_probabilities(
    draft_picks_df: pd.DataFrame,
    *,
    owner_id: int,
    target_player_ids: Iterable[int],
    iterations: int,
) -> pd.DataFrame:
    picks = draft_picks_df[draft_picks_df["owner_id"] == owner_id].copy()
    grouped = picks.groupby("player_id", as_index=False).agg(hit_count=("iteration", "nunique"))
    requested = pd.DataFrame({"player_id": list(target_player_ids)})
    merged = requested.merge(grouped, on="player_id", how="left")
    merged["hit_count"] = merged["hit_count"].fillna(0)
    merged["probability"] = merged["hit_count"] / max(iterations, 1)
    return merged