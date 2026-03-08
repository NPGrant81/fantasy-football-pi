from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models


STAT_KEY_ALIASES: dict[str, list[str]] = {
    "passing_yards": ["passing_yards", "pass_yards", "pass_yds"],
    "passing_tds": ["passing_tds", "pass_tds", "pass_touchdowns"],
    "rushing_yards": ["rushing_yards", "rush_yards", "rush_yds"],
    "rushing_tds": ["rushing_tds", "rush_tds", "rush_touchdowns"],
    "receiving_yards": ["receiving_yards", "rec_yards", "rec_yds"],
    "receiving_tds": ["receiving_tds", "rec_tds", "rec_touchdowns"],
    "receptions": ["receptions", "rec", "catches"],
    "interceptions": ["interceptions", "ints", "interceptions_thrown"],
    "fumbles_lost": ["fumbles_lost", "fumbles"],
    "two_point_conversions": ["two_point_conversions", "2pt", "two_point"],
    "fantasy_points": ["fantasy_points", "points", "final_score"],
}


@dataclass
class CalculatedRuleResult:
    rule_id: int | None
    event_name: str
    category: str
    calculation_type: str
    stat_key: str
    stat_value: float
    points: float


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_position(position: str | None) -> str:
    if not position:
        return "ALL"
    normalized = position.upper().strip()
    if normalized in {"DEF", "D/ST", "DST"}:
        return "DST"
    return normalized


def _rule_applies_to_position(rule: models.ScoringRule, position: str) -> bool:
    normalized = _normalize_position(position)
    positions = [_normalize_position(item) for item in (rule.applicable_positions or [])]
    if not positions:
        return True
    return normalized in positions or "ALL" in positions or "FLEX" in positions


def _candidate_stat_keys(event_name: str, category: str) -> list[str]:
    seeds = [event_name, category, f"{category}_{event_name}"]
    candidates: list[str] = []

    for seed in seeds:
        normalized = seed.lower().strip().replace(" ", "_")
        if not normalized:
            continue
        if normalized not in candidates:
            candidates.append(normalized)
        for alias in STAT_KEY_ALIASES.get(normalized, []):
            if alias not in candidates:
                candidates.append(alias)

    return candidates


def _resolve_stat_value(stats: dict[str, Any], event_name: str, category: str) -> tuple[str, float]:
    candidates = _candidate_stat_keys(event_name, category)
    for key in candidates:
        if key in stats:
            return key, _to_float(stats.get(key), 0.0)
    return candidates[0] if candidates else event_name, 0.0


def _calculate_rule_points(rule: models.ScoringRule, observed_value: float) -> float:
    lower = _to_float(rule.range_min, 0.0)
    upper = _to_float(rule.range_max, 999999.0)
    point_value = _to_float(rule.point_value, 0.0)
    calc_type = (rule.calculation_type or "flat_bonus").lower().strip()

    if observed_value < lower or observed_value > upper:
        return 0.0

    if calc_type in {"flat_bonus", "event_bonus", "threshold_bonus"}:
        return point_value

    if calc_type in {"per_unit", "decimal", "ppr", "half_ppr", "multiplier"}:
        return observed_value * point_value

    if calc_type in {"tiered", "yardage_tier"}:
        # Tier scoring applies to each unit above the floor within the matched range.
        units = max(observed_value - lower, 0.0)
        return units * point_value

    return point_value


def active_scoring_rules_for_league(
    db: Session,
    *,
    league_id: int,
    season_year: int | None = None,
) -> list[models.ScoringRule]:
    query = db.query(models.ScoringRule).filter(
        models.ScoringRule.league_id == league_id,
        models.ScoringRule.is_active.is_(True),
    )

    if season_year is not None:
        query = query.filter(
            (models.ScoringRule.season_year == season_year) | models.ScoringRule.season_year.is_(None)
        )

    return query.order_by(models.ScoringRule.id.asc()).all()


def calculate_points_for_stats(
    *,
    stats: dict[str, Any],
    position: str,
    rules: list[models.ScoringRule],
) -> tuple[float, list[CalculatedRuleResult]]:
    total = 0.0
    breakdown: list[CalculatedRuleResult] = []

    for rule in rules:
        if not _rule_applies_to_position(rule, position):
            continue

        stat_key, value = _resolve_stat_value(stats, rule.event_name, rule.category)
        points = _calculate_rule_points(rule, value)
        if points == 0:
            continue

        rounded_points = round(points, 4)
        total += rounded_points
        breakdown.append(
            CalculatedRuleResult(
                rule_id=rule.id,
                event_name=rule.event_name,
                category=rule.category,
                calculation_type=rule.calculation_type,
                stat_key=stat_key,
                stat_value=round(value, 4),
                points=rounded_points,
            )
        )

    return round(total, 4), breakdown


def calculate_player_week_points(
    db: Session,
    *,
    league_id: int,
    player_id: int,
    season: int,
    week: int,
    position: str | None = None,
    season_year: int | None = None,
) -> tuple[float, list[CalculatedRuleResult], dict[str, Any]]:
    rules = active_scoring_rules_for_league(db, league_id=league_id, season_year=season_year)

    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    resolved_position = _normalize_position(position or (player.position if player else None))

    weekly_stat = (
        db.query(models.PlayerWeeklyStat)
        .filter(
            models.PlayerWeeklyStat.player_id == player_id,
            models.PlayerWeeklyStat.season == season,
            models.PlayerWeeklyStat.week == week,
        )
        .order_by(models.PlayerWeeklyStat.id.desc())
        .first()
    )

    if not weekly_stat:
        return 0.0, [], {}

    stats_payload = dict(weekly_stat.stats or {})
    if weekly_stat.fantasy_points is not None:
        stats_payload.setdefault("fantasy_points", _to_float(weekly_stat.fantasy_points))

    total, breakdown = calculate_points_for_stats(stats=stats_payload, position=resolved_position, rules=rules)
    if not rules and weekly_stat.fantasy_points is not None:
        total = round(_to_float(weekly_stat.fantasy_points), 4)

    return total, breakdown, stats_payload


def recalculate_matchup_scores(
    db: Session,
    *,
    matchup: models.Matchup,
    season: int,
    season_year: int | None = None,
) -> dict[str, Any]:
    if matchup.league_id is None:
        raise ValueError("matchup.league_id is required for scoring recalculation")

    league_filter = or_(
        models.DraftPick.league_id == matchup.league_id,
        models.DraftPick.league_id.is_(None),
    )
    home_starters = (
        db.query(models.DraftPick)
        .filter(
            models.DraftPick.owner_id == matchup.home_team_id,
            models.DraftPick.current_status == "STARTER",
            league_filter,
        )
        .all()
    )
    away_starters = (
        db.query(models.DraftPick)
        .filter(
            models.DraftPick.owner_id == matchup.away_team_id,
            models.DraftPick.current_status == "STARTER",
            league_filter,
        )
        .all()
    )

    def score_lineup(lineup: list[models.DraftPick]) -> tuple[float, int]:
        total = 0.0
        contributors = 0
        for pick in lineup:
            points, _, _ = calculate_player_week_points(
                db,
                league_id=matchup.league_id,
                player_id=pick.player_id,
                season=season,
                week=matchup.week,
                season_year=season_year,
            )
            if points != 0:
                contributors += 1
            total += points
        return round(total, 4), contributors

    home_total, home_contributors = score_lineup(home_starters)
    away_total, away_contributors = score_lineup(away_starters)

    matchup.home_score = home_total
    matchup.away_score = away_total
    matchup.game_status = "FINAL"
    matchup.is_completed = True

    return {
        "matchup_id": matchup.id,
        "league_id": matchup.league_id,
        "season": season,
        "week": matchup.week,
        "home_team_id": matchup.home_team_id,
        "away_team_id": matchup.away_team_id,
        "home_score": home_total,
        "away_score": away_total,
        "home_contributors": home_contributors,
        "away_contributors": away_contributors,
    }


def recalculate_league_week_scores(
    db: Session,
    *,
    league_id: int,
    week: int,
    season: int,
    season_year: int | None = None,
) -> list[dict[str, Any]]:
    matchups = (
        db.query(models.Matchup)
        .filter(
            models.Matchup.league_id == league_id,
            models.Matchup.week == week,
        )
        .order_by(models.Matchup.id.asc())
        .all()
    )

    results: list[dict[str, Any]] = []
    for matchup in matchups:
        results.append(
            recalculate_matchup_scores(
                db,
                matchup=matchup,
                season=season,
                season_year=season_year,
            )
        )

    return results
