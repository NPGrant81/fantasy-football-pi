from __future__ import annotations

from collections import defaultdict
import math
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from .. import models_draft_value as dv_models
from ..services.player_service import (
    _active_player_or_unsynced_filter,
    canonical_player_key,
    canonical_player_rank,
    dedupe_players,
    is_valid_player_row,
    ALLOWED_POSITIONS,
)


def _serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        from marshmallow import Schema, fields  # type: ignore
    except Exception:
        return rows

    class HistoricalRankingSchema(Schema):
        player_id = fields.Integer(required=True)
        player_name = fields.String(required=True)
        position = fields.String(allow_none=True)
        season = fields.Integer(required=True)
        rank = fields.Integer(required=True)
        predicted_auction_value = fields.Float(required=True)
        value_over_replacement = fields.Float(required=True)
        consensus_tier = fields.String(allow_none=True)
        final_score = fields.Float(required=True)
        league_position_weight = fields.Float(required=True)
        owner_position_affinity = fields.Float(required=True)
        owner_player_affinity = fields.Float(required=True)
        keeper_scarcity_boost = fields.Float(required=True)
        availability_factor = fields.Float(required=True)
        scoring_consistency_factor = fields.Float(required=True)
        late_start_consistency_factor = fields.Float(required=True)
        injury_split_factor = fields.Float(required=True)
        team_change_factor = fields.Float(required=True)
        price_min = fields.Float(allow_none=True)
        price_avg = fields.Float(allow_none=True)
        price_max = fields.Float(allow_none=True)
        source_count = fields.Integer(allow_none=True)
        sources = fields.List(fields.String(), allow_none=True)
        adp = fields.Float(allow_none=True)

    schema = HistoricalRankingSchema(many=True)
    return schema.dump(rows)


def _build_league_position_weights(db: Session, *, league_id: int | None) -> dict[str, float]:
    base = {"QB": 1.0, "RB": 1.0, "WR": 1.0, "TE": 1.0, "K": 1.0, "DEF": 1.0}
    if not league_id:
        return base

    rules = (
        db.query(models.ScoringRule)
        .filter(models.ScoringRule.league_id == league_id)
        .all()
    )
    if not rules:
        return base

    weighted_points = {key: 0.0 for key in base.keys()}
    for rule in rules:
        positions = rule.applicable_positions or []
        point_value = float(rule.point_value or 0)
        if not positions:
            continue
        for pos in positions:
            normalized = str(pos).upper().strip()
            if normalized in weighted_points:
                weighted_points[normalized] += abs(point_value)

    max_points = max(weighted_points.values()) if weighted_points else 0
    if max_points <= 0:
        return base

    for pos in base.keys():
        base[pos] = 0.75 + (weighted_points[pos] / max_points) * 0.75
    return base


def _build_owner_position_affinity(
    db: Session,
    *,
    league_id: int | None,
    owner_id: int | None,
) -> dict[str, float]:
    base = {"QB": 1.0, "RB": 1.0, "WR": 1.0, "TE": 1.0, "K": 1.0, "DEF": 1.0}
    if not league_id or not owner_id:
        return base

    picks = (
        db.query(models.DraftPick, models.Player)
        .join(models.Player, models.Player.id == models.DraftPick.player_id)
        .filter(
            models.DraftPick.league_id == league_id,
            models.DraftPick.owner_id == owner_id,
        )
        .all()
    )
    if not picks:
        return base

    spend_by_pos = {key: 0.0 for key in base.keys()}
    count_by_pos = {key: 0 for key in base.keys()}
    for pick, player in picks:
        pos = (player.position or "").upper()
        if pos not in spend_by_pos:
            continue
        spend_by_pos[pos] += float(pick.amount or 0)
        count_by_pos[pos] += 1

    max_spend = max(spend_by_pos.values()) if spend_by_pos else 0
    max_count = max(count_by_pos.values()) if count_by_pos else 0
    if max_spend <= 0 and max_count <= 0:
        return base

    for pos in base.keys():
        spend_component = (spend_by_pos[pos] / max_spend) if max_spend > 0 else 0
        count_component = (count_by_pos[pos] / max_count) if max_count > 0 else 0
        base[pos] = 0.8 + (0.6 * spend_component + 0.4 * count_component) * 0.8
    return base


def _build_owner_player_affinity(
    db: Session,
    *,
    league_id: int | None,
    owner_id: int | None,
) -> dict[int, float]:
    if not league_id or not owner_id:
        return {}

    rows = (
        db.query(models.DraftPick.player_id, func.count(models.DraftPick.id))
        .filter(
            models.DraftPick.league_id == league_id,
            models.DraftPick.owner_id == owner_id,
        )
        .group_by(models.DraftPick.player_id)
        .all()
    )
    if not rows:
        return {}

    max_count = max(int(count or 0) for _, count in rows)
    if max_count <= 1:
        return {}

    affinity: dict[int, float] = {}
    for player_id, count in rows:
        if not player_id:
            continue
        repeats = max(0, int(count) - 1)
        affinity[int(player_id)] = 1.0 + (repeats / max_count) * 0.4
    return affinity


def _build_keeper_scarcity_boost(
    db: Session,
    *,
    league_id: int | None,
    season: int,
) -> dict[str, float]:
    base = {"QB": 1.0, "RB": 1.0, "WR": 1.0, "TE": 1.0, "K": 1.0, "DEF": 1.0}
    if not league_id:
        return base

    keepers = (
        db.query(models.Keeper, models.Player)
        .join(models.Player, models.Player.id == models.Keeper.player_id)
        .filter(
            models.Keeper.league_id == league_id,
            models.Keeper.season == season - 1,
            (
                (models.Keeper.status == "locked")
                | (models.Keeper.approved_by_commish.is_(True))
            ),
        )
        .all()
    )
    if not keepers:
        return base

    counts = {key: 0 for key in base.keys()}
    for _, player in keepers:
        pos = (player.position or "").upper()
        if pos in counts:
            counts[pos] += 1

    max_count = max(counts.values()) if counts else 0
    if max_count <= 0:
        return base

    for pos in base.keys():
        base[pos] = 1.0 + (counts[pos] / max_count) * 0.3
    return base


def _build_availability_factor(
    db: Session,
    *,
    season: int,
) -> dict[int, float]:
    rows = (
        db.query(models.PlayerWeeklyStat.player_id, func.count(models.PlayerWeeklyStat.id))
        .filter(models.PlayerWeeklyStat.season == season - 1)
        .group_by(models.PlayerWeeklyStat.player_id)
        .all()
    )
    if not rows:
        return {}

    max_games = max(int(count or 0) for _, count in rows)
    if max_games <= 0:
        return {}

    factors: dict[int, float] = {}
    for player_id, games in rows:
        if not player_id:
            continue
        played_ratio = min(1.0, max(0.0, float(games) / float(max_games)))
        factors[int(player_id)] = 0.85 + played_ratio * 0.25
    return factors


def _stddev(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def _extract_team_code(stats_blob: Any) -> str | None:
    if not isinstance(stats_blob, dict):
        return None
    for key in ("team", "nfl_team", "team_abbr", "teamAbbr", "pro_team"):
        value = stats_blob.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def _build_consistency_factors(
    db: Session,
    *,
    season: int,
) -> dict[int, dict[str, float]]:
    rows = (
        db.query(models.PlayerWeeklyStat)
        .filter(models.PlayerWeeklyStat.season == season - 1)
        .order_by(models.PlayerWeeklyStat.player_id.asc(), models.PlayerWeeklyStat.week.asc())
        .all()
    )
    if not rows:
        return {}

    grouped: dict[int, list[models.PlayerWeeklyStat]] = {}
    for row in rows:
        if not row.player_id:
            continue
        grouped.setdefault(int(row.player_id), []).append(row)

    factors: dict[int, dict[str, float]] = {}
    for player_id, entries in grouped.items():
        weekly_points = [float(entry.fantasy_points or 0) for entry in entries]
        if not weekly_points:
            continue

        mean_points = sum(weekly_points) / len(weekly_points)
        deviation = _stddev(weekly_points)
        normalized_deviation = deviation / (mean_points + 1.0)
        scoring_consistency_factor = max(0.8, min(1.25, 1.15 - normalized_deviation * 0.6))

        first_week = int(entries[0].week or 1)
        late_start_consistency_factor = 1.0
        if first_week >= 7 and len(weekly_points) >= 4:
            late_deviation = _stddev(weekly_points)
            late_norm = late_deviation / (mean_points + 1.0)
            late_start_consistency_factor = max(0.9, min(1.15, 1.1 - late_norm * 0.4))

        observed_weeks = [int(entry.week or 0) for entry in entries if entry.week is not None]
        injury_split_factor = 1.0
        if len(observed_weeks) >= 4:
            gaps = [
                idx
                for idx in range(1, len(observed_weeks))
                if observed_weeks[idx] - observed_weeks[idx - 1] > 1
            ]
            if gaps:
                split_idx = gaps[-1]
                before = weekly_points[:split_idx]
                after = weekly_points[split_idx:]
                if before and after:
                    before_avg = sum(before) / len(before)
                    after_avg = sum(after) / len(after)
                    delta = (after_avg - before_avg) / (abs(before_avg) + 1.0)
                    injury_split_factor = max(0.85, min(1.2, 1.0 + delta * 0.25))

        team_change_factor = 1.0
        team_sequence = [_extract_team_code(entry.stats) for entry in entries]
        valid_teams = [team for team in team_sequence if team]
        if len(valid_teams) >= 2:
            first_team = valid_teams[0]
            change_index = None
            for idx, team in enumerate(team_sequence):
                if team and team != first_team:
                    change_index = idx
                    break
            if change_index is not None and change_index > 0:
                pre_change = weekly_points[:change_index]
                post_change = weekly_points[change_index:]
                if pre_change and post_change:
                    pre_avg = sum(pre_change) / len(pre_change)
                    post_avg = sum(post_change) / len(post_change)
                    delta = (post_avg - pre_avg) / (abs(pre_avg) + 1.0)
                    team_change_factor = max(0.85, min(1.2, 1.0 + delta * 0.2))

        factors[player_id] = {
            "scoring_consistency_factor": float(scoring_consistency_factor),
            "late_start_consistency_factor": float(late_start_consistency_factor),
            "injury_split_factor": float(injury_split_factor),
            "team_change_factor": float(team_change_factor),
        }

    return factors


def _fallback_draft_value_rows_from_players(
    db: Session,
    *,
    season: int,
    normalized_position: str,
) -> list[tuple[Any, models.Player]]:
    position_filter = ALLOWED_POSITIONS
    players_query = db.query(models.Player).filter(
        models.Player.position.in_(position_filter),
        _active_player_or_unsynced_filter(db),
    )
    if normalized_position:
        players_query = players_query.filter(models.Player.position == normalized_position)

    raw_players = players_query.order_by(models.Player.name, models.Player.id.desc()).all()
    # Apply name/team validity check and deduplicate identical player identities
    players = dedupe_players([p for p in raw_players if is_valid_player_row(p)])
    if not players:
        return []

    per_position_points: dict[str, list[float]] = {}
    for player in players:
        pos = (player.position or "UNK").upper()
        projected = float(player.projected_points or 0.0)
        if projected <= 0 and player.adp is not None and float(player.adp) > 0:
            projected = max(8.0, 300.0 - float(player.adp))
        if projected > 0:
            per_position_points.setdefault(pos, []).append(projected)

    replacement_by_position: dict[str, float] = {}
    for pos, points in per_position_points.items():
        if not points:
            replacement_by_position[pos] = 0.0
            continue
        sorted_points = sorted(points, reverse=True)
        replacement_idx = min(len(sorted_points) - 1, max(0, int(len(sorted_points) * 0.6)))
        replacement_by_position[pos] = float(sorted_points[replacement_idx])

    class _FallbackDraftValue:
        def __init__(self, *, avg_auction_value: float, value_over_replacement: float, consensus_tier: str):
            self.season = season
            self.avg_auction_value = avg_auction_value
            self.value_over_replacement = value_over_replacement
            self.consensus_tier = consensus_tier

    fallback_rows: list[tuple[Any, models.Player]] = []
    for player in players:
        pos = (player.position or "UNK").upper()
        projected = float(player.projected_points or 0.0)
        if projected <= 0 and player.adp is not None and float(player.adp) > 0:
            projected = max(8.0, 300.0 - float(player.adp))
        if projected <= 0:
            # Skip stale identities that have no ADP/projected-points signal.
            continue

        replacement = float(replacement_by_position.get(pos, 0.0))
        value_over_replacement = max(0.0, projected - replacement)
        auction_value = max(1.0, projected * 0.11 + value_over_replacement * 0.09)

        if auction_value >= 45:
            tier = "S"
        elif auction_value >= 30:
            tier = "A"
        elif auction_value >= 18:
            tier = "B"
        elif auction_value >= 8:
            tier = "C"
        else:
            tier = "D"

        fallback_rows.append(
            (
                _FallbackDraftValue(
                    avg_auction_value=float(round(auction_value, 2)),
                    value_over_replacement=float(round(value_over_replacement, 2)),
                    consensus_tier=tier,
                ),
                player,
            )
        )

    return fallback_rows


def _dedupe_ranking_rows(
    rows: list[tuple[Any, models.Player]],
) -> list[tuple[Any, models.Player]]:
    selected: dict[tuple, tuple[Any, models.Player]] = {}

    def _ranking_rank(draft_value: Any, player: models.Player) -> tuple[float, float, tuple[int, int, int]]:
        return (
            float(getattr(draft_value, "avg_auction_value", 0.0) or 0.0),
            float(getattr(draft_value, "value_over_replacement", 0.0) or 0.0),
            canonical_player_rank(player),
        )

    for draft_value, player in rows:
        key = canonical_player_key(player)
        current = selected.get(key)
        if current is None or _ranking_rank(draft_value, player) > _ranking_rank(*current):
            selected[key] = (draft_value, player)

    return list(selected.values())


def _merge_missing_fallback_rows(
    db: Session,
    *,
    season: int,
    normalized_position: str,
    base_rows: list[tuple[Any, models.Player]],
) -> list[tuple[Any, models.Player]]:
    """Ensure partial seasonal datasets still include all active player identities.

    When a season has some DraftValue rows, we keep those authoritative values but
    add fallback rows for identities that are missing entirely.
    """
    if not base_rows:
        return _fallback_draft_value_rows_from_players(
            db,
            season=season,
            normalized_position=normalized_position,
        )

    fallback_rows = _fallback_draft_value_rows_from_players(
        db,
        season=season,
        normalized_position=normalized_position,
    )
    if not fallback_rows:
        return base_rows

    existing_keys = {
        canonical_player_key(player)
        for _, player in base_rows
    }
    merged_rows = list(base_rows)
    for fallback_row in fallback_rows:
        _, fallback_player = fallback_row
        if canonical_player_key(fallback_player) in existing_keys:
            continue
        merged_rows.append(fallback_row)

    return _dedupe_ranking_rows(merged_rows)


def _build_source_price_stats(
    db: Session,
    *,
    season: int,
) -> dict[int, dict[str, Any]]:
    """
    Aggregate PlatformProjection rows for *season* into per-player price stats:
    min, avg, and max auction value across all sources that reported one.

    Returns {player_id: {price_min, price_avg, price_max, source_count, sources}}.
    Returns an empty dict if no projection rows exist for the season — callers
    should treat a missing key as "no external price data yet".
    """
    price_rows = (
        db.query(
            dv_models.PlatformProjection.player_id,
            func.min(dv_models.PlatformProjection.auction_value).label("price_min"),
            func.avg(dv_models.PlatformProjection.auction_value).label("price_avg"),
            func.max(dv_models.PlatformProjection.auction_value).label("price_max"),
            func.count(dv_models.PlatformProjection.id).label("source_count"),
        )
        .filter(
            dv_models.PlatformProjection.season == season,
            dv_models.PlatformProjection.auction_value.isnot(None),
            dv_models.PlatformProjection.auction_value > 0,
        )
        .group_by(dv_models.PlatformProjection.player_id)
        .all()
    )

    if not price_rows:
        return {}

    source_rows = (
        db.query(
            dv_models.PlatformProjection.player_id,
            dv_models.PlatformProjection.source,
        )
        .filter(
            dv_models.PlatformProjection.season == season,
            dv_models.PlatformProjection.auction_value.isnot(None),
            dv_models.PlatformProjection.auction_value > 0,
        )
        .distinct()
        .all()
    )

    sources_by_player: dict[int, list[str]] = defaultdict(list)
    for pid, src in source_rows:
        if pid is not None and src:
            sources_by_player[int(pid)].append(src)

    stats: dict[int, dict[str, Any]] = {}
    for row in price_rows:
        if row.player_id is None:
            continue
        pid = int(row.player_id)
        stats[pid] = {
            "price_min": float(row.price_min) if row.price_min is not None else None,
            "price_avg": round(float(row.price_avg), 2) if row.price_avg is not None else None,
            "price_max": float(row.price_max) if row.price_max is not None else None,
            "source_count": int(row.source_count) if row.source_count is not None else 0,
            "sources": sorted(sources_by_player.get(pid, [])),
        }
    return stats


def get_historical_rankings(
    db: Session,
    *,
    season: int,
    limit: int = 40,
    league_id: int | None = None,
    owner_id: int | None = None,
    position: str | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 200))

    query = (
        db.query(dv_models.DraftValue, models.Player)
        .join(models.Player, models.Player.id == dv_models.DraftValue.player_id)
        .filter(
            dv_models.DraftValue.season == season,
            models.Player.position.in_(ALLOWED_POSITIONS),
            _active_player_or_unsynced_filter(db),
        )
    )

    normalized_position = (position or "").upper().strip()
    if normalized_position:
        query = query.filter(models.Player.position == normalized_position)

    query_rows = _dedupe_ranking_rows(query.all())
    query_rows = _merge_missing_fallback_rows(
        db,
        season=season,
        normalized_position=normalized_position,
        base_rows=query_rows,
    )

    league_weights = _build_league_position_weights(db, league_id=league_id)
    owner_position_affinity = _build_owner_position_affinity(
        db,
        league_id=league_id,
        owner_id=owner_id,
    )
    owner_player_affinity = _build_owner_player_affinity(
        db,
        league_id=league_id,
        owner_id=owner_id,
    )
    keeper_scarcity = _build_keeper_scarcity_boost(db, league_id=league_id, season=season)
    availability = _build_availability_factor(db, season=season)
    consistency_factors = _build_consistency_factors(db, season=season)
    source_price_stats = _build_source_price_stats(db, season=season)

    scored_payload: list[dict[str, Any]] = []
    for draft_value, player in query_rows:
        pos = (player.position or "UNK").upper()
        base_value = float(draft_value.avg_auction_value or 0)
        vor = float(draft_value.value_over_replacement or 0)

        league_weight = float(league_weights.get(pos, 1.0))
        owner_pos_weight = float(owner_position_affinity.get(pos, 1.0))
        owner_player_weight = float(owner_player_affinity.get(int(player.id), 1.0))
        keeper_weight = float(keeper_scarcity.get(pos, 1.0))
        availability_weight = float(availability.get(int(player.id), 1.0))
        consistency = consistency_factors.get(int(player.id), {})
        scoring_consistency_factor = float(consistency.get("scoring_consistency_factor", 1.0))
        late_start_consistency_factor = float(consistency.get("late_start_consistency_factor", 1.0))
        injury_split_factor = float(consistency.get("injury_split_factor", 1.0))
        team_change_factor = float(consistency.get("team_change_factor", 1.0))
        price_stats = source_price_stats.get(int(player.id), {})

        final_score = (
            base_value * 0.55
            + vor * 0.45
        ) * (
            league_weight
            * owner_pos_weight
            * owner_player_weight
            * keeper_weight
            * availability_weight
            * scoring_consistency_factor
            * late_start_consistency_factor
            * injury_split_factor
            * team_change_factor
        )

        scored_payload.append(
            {
                "player_id": int(player.id),
                "player_name": player.name,
                "position": player.position,
                "season": int(draft_value.season),
                "predicted_auction_value": float(draft_value.avg_auction_value or 0),
                "value_over_replacement": float(draft_value.value_over_replacement or 0),
                "consensus_tier": draft_value.consensus_tier,
                "final_score": float(final_score),
                "league_position_weight": league_weight,
                "owner_position_affinity": owner_pos_weight,
                "owner_player_affinity": owner_player_weight,
                "keeper_scarcity_boost": keeper_weight,
                "availability_factor": availability_weight,
                "scoring_consistency_factor": scoring_consistency_factor,
                "late_start_consistency_factor": late_start_consistency_factor,
                "injury_split_factor": injury_split_factor,
                "team_change_factor": team_change_factor,
                "price_min": price_stats.get("price_min"),
                "price_avg": price_stats.get("price_avg"),
                "price_max": price_stats.get("price_max"),
                "source_count": price_stats.get("source_count", 0),
                "sources": price_stats.get("sources", []),
                "adp": float(player.adp) if player.adp is not None else None,
            }
        )

    ranked = sorted(
        scored_payload,
        key=lambda row: (row["final_score"], row["predicted_auction_value"]),
        reverse=True,
    )[:safe_limit]

    for index, row in enumerate(ranked, start=1):
        row["rank"] = index

    return _serialize_rows(ranked)
