from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import sqlalchemy as sa
from typing import List
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..database import get_db
from .. import models
# import organizer helper from team router for roster-strength computation
from .team import organize_roster
from ..services.player_service import normalize_display_name as _normalize_player_name
from ..services.season_outlook_service import build_post_draft_outlook
from ..schemas.season_outlook import PostDraftOutlookResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])

MIN_VALID_SEASON_YEAR = 2000
MAX_VALID_SEASON_YEAR = datetime.now().year + 2


class VisitEventIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timestamp: datetime | None = None
    path: str = Field(min_length=1, max_length=512)
    userId: int | None = Field(default=None, ge=1)
    sessionId: str = Field(min_length=8, max_length=128)
    userAgent: str | None = Field(default=None, max_length=512)
    referrer: str | None = Field(default=None, max_length=1024)

    @field_validator("path")
    @classmethod
    def _normalize_path(cls, value: str) -> str:
        path = (value or "").strip()
        if not path.startswith("/"):
            raise ValueError("path must start with '/'")
        return path


@router.post('/visit')
def record_site_visit(payload: VisitEventIn, db: Session = Depends(get_db)):
    user_id = payload.userId
    if user_id is not None:
        user_exists = db.query(models.User.id).filter(models.User.id == user_id).first()
        if user_exists is None:
            user_id = None

    visit = models.SiteVisit(
        path=payload.path,
        user_id=user_id,
        session_id=payload.sessionId,
        user_agent=payload.userAgent,
        referrer=payload.referrer,
        client_timestamp=payload.timestamp,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return {
        "id": visit.id,
        "timestamp": visit.timestamp.isoformat() if visit.timestamp else None,
    }


def _safe_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sorted_owner_pair(first, second) -> tuple[int, int] | None:
    a = _safe_int(first)
    b = _safe_int(second)
    if a is None or b is None:
        return None
    return tuple(sorted((a, b)))


def _resolved_season(season: int | None) -> int:
    if season is None:
        season = datetime.now().year

    # Direct function calls in tests can pass FastAPI Query defaults.
    if not isinstance(season, (int, float, str)):
        season = getattr(season, "default", None)
        if season is None:
            season = datetime.now().year

    normalized = int(season)
    if normalized < MIN_VALID_SEASON_YEAR or normalized > MAX_VALID_SEASON_YEAR:
        raise HTTPException(
            status_code=400,
            detail=f"season must be between {MIN_VALID_SEASON_YEAR} and {MAX_VALID_SEASON_YEAR}",
        )
    return normalized


def _active_scoring_profile(db: Session, league_id: int, season: int) -> dict:
    rules = (
        db.query(models.ScoringRule)
        .filter(
            models.ScoringRule.league_id == league_id,
            models.ScoringRule.is_active.is_(True),
            (models.ScoringRule.season_year == season)
            | models.ScoringRule.season_year.is_(None),
        )
        .all()
    )

    template_ids = sorted({int(rule.template_id) for rule in rules if rule.template_id is not None})
    template_name = None
    if len(template_ids) == 1:
        template = (
            db.query(models.ScoringTemplate)
            .filter(models.ScoringTemplate.id == template_ids[0])
            .first()
        )
        template_name = template.name if template else None

    if not rules:
        profile_name = "No Active Scoring Rules"
    elif template_name:
        profile_name = template_name
    elif len(template_ids) > 1:
        profile_name = "Mixed Template Rules"
    else:
        profile_name = "Custom Rules"

    return {
        "profile_name": profile_name,
        "template_id": template_ids[0] if len(template_ids) == 1 else None,
        "rules_count": len(rules),
    }


def _analytics_meta(db: Session, *, metric: str, league_id: int, season: int) -> dict:
    return {
        "metric": metric,
        "league_id": league_id,
        "season": season,
        "scoring_profile": _active_scoring_profile(db, league_id, season),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def format_leaderboard_row(row) -> dict:
    eff = float(row.avg_efficiency) if row.avg_efficiency is not None else 0.0
    if eff >= 0.95:
        personality = 'The Tactician'
    elif eff >= 0.85:
        personality = 'Solid Starter'
    elif eff >= 0.75:
        personality = 'Coin Tosser'
    else:
        personality = 'Bench Warmer'

    return {
        'manager_id': row.manager_id,
        'actual': float(row.actual),
        'optimal': float(row.optimal),
        'avg_efficiency': eff,
        'efficiency_display': f"{eff * 100:.1f}%",
        'total_regret': float(row.total_regret or 0),
        'personality': personality,
    }


@router.get('/league/{league_id}/leaderboard')
def get_efficiency_leaderboard(
    league_id: int,
    season: int = Query(None, description="Season year (defaults to current year)"),
    db: Session = Depends(get_db),
):
    season = _resolved_season(season)

    try:
        query = (
            db.query(
                models.ManagerEfficiency.manager_id,
                sa.func.sum(models.ManagerEfficiency.actual_points_total).label('actual'),
                sa.func.sum(models.ManagerEfficiency.optimal_points_total).label('optimal'),
                sa.func.avg(models.ManagerEfficiency.efficiency_rating).label('avg_efficiency'),
                sa.func.sum(models.ManagerEfficiency.points_left_on_bench).label('total_regret'),
            )
            .filter(models.ManagerEfficiency.league_id == league_id, models.ManagerEfficiency.season == season)
            .group_by(models.ManagerEfficiency.manager_id)
            .order_by(sa.desc('avg_efficiency'))
        )
        rows = query.all()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    formatted = [format_leaderboard_row(r) for r in rows]
    return {
        "rows": formatted,
        "meta": _analytics_meta(
            db,
            metric="manager_efficiency_leaderboard",
            league_id=league_id,
            season=season,
        ),
    }


@router.get('/roster-strength')
def get_roster_strength(
    league_id: int,
    owner_id: int,
    other_owner_id: int | None = None,
    season: int = Query(None, description="Season year (defaults to current year)"),
    db: Session = Depends(get_db),
):
    """Return positional counts for owner (and optional other owner)."""
    # fetch picks for primary owner
    picks = (
        db.query(models.DraftPick)
        .filter(models.DraftPick.league_id == league_id, models.DraftPick.owner_id == owner_id)
        .all()
    )
    roster = organize_roster(picks, db)
    def compute_counts(lst):
        counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "DEF": 0, "K": 0}
        for p in lst:
            if p.position in counts and p.is_starter:
                counts[p.position] += 1
        return counts

    result = {owner_id: compute_counts(roster)}
    if other_owner_id is not None:
        other_picks = (
            db.query(models.DraftPick)
            .filter(models.DraftPick.league_id == league_id, models.DraftPick.owner_id == other_owner_id)
            .all()
        )
        other_roster = organize_roster(other_picks, db)
        result[other_owner_id] = compute_counts(other_roster)
    resolved_season = _resolved_season(season)
    return {
        "rows": result,
        "meta": _analytics_meta(
            db,
            metric="roster_strength",
            league_id=league_id,
            season=resolved_season,
        ),
    }


@router.get('/league/{league_id}/weekly-stats')
def get_weekly_stats(
    league_id: int,
    manager_id: int,
    season: int = Query(None),
    db: Session = Depends(get_db),
):
    season = _resolved_season(season)

    stats = (
        db.query(models.ManagerEfficiency)
        .filter(
            models.ManagerEfficiency.league_id == league_id,
            models.ManagerEfficiency.manager_id == manager_id,
            models.ManagerEfficiency.season == season,
        )
        .order_by(models.ManagerEfficiency.week)
        .all()
    )

    rows = [
        {
            'week': r.week,
            'actual': float(r.actual_points_total),
            'max': float(r.optimal_points_total),
            'efficiency': float(r.efficiency_rating),
            'points_left': float(r.points_left_on_bench or 0),
        }
        for r in stats
    ]
    return {
        "rows": rows,
        "meta": _analytics_meta(
            db,
            metric="manager_weekly_stats",
            league_id=league_id,
            season=season,
        ),
    }


@router.get('/league/{league_id}/draft-value')
def get_draft_value_data(
    league_id: int,
    season: int = Query(None, description="Season year (defaults to current year)"),
    limit: int = Query(60, ge=10, le=200),
    db: Session = Depends(get_db),
):
    resolved_season = _resolved_season(season)

    player_ids = [
        row[0]
        for row in (
            db.query(models.DraftPick.player_id)
            .filter(
                models.DraftPick.league_id == league_id,
                models.DraftPick.player_id.isnot(None),
            )
            .distinct()
            .all()
        )
        if row[0] is not None
    ]

    player_query = db.query(models.Player).filter(models.Player.position.in_(["QB", "RB", "WR", "TE"]))
    if player_ids:
        player_query = player_query.filter(models.Player.id.in_(player_ids))

    players = player_query.order_by(models.Player.projected_points.desc(), models.Player.adp.asc()).limit(limit).all()
    if not players:
        players = (
            db.query(models.Player)
            .filter(models.Player.position.in_(["QB", "RB", "WR", "TE"]))
            .order_by(models.Player.projected_points.desc(), models.Player.adp.asc())
            .limit(limit)
            .all()
        )

    fallback_totals = {
        int(player_id): float(total or 0.0)
        for player_id, total in (
            db.query(
                models.PlayerWeeklyStat.player_id,
                sa.func.sum(models.PlayerWeeklyStat.fantasy_points),
            )
            .filter(models.PlayerWeeklyStat.season == resolved_season - 1)
            .group_by(models.PlayerWeeklyStat.player_id)
            .all()
        )
        if player_id is not None
    }

    rows = []
    for player in players:
        projected_points = float(player.projected_points or 0.0)
        if projected_points <= 0:
            projected_points = float(fallback_totals.get(int(player.id), 0.0))

        adp = float(player.adp or 0.0)
        normalized_adp = adp if adp > 0 else 200.0
        value_score = projected_points / max(normalized_adp, 1.0)

        rows.append(
            {
                "player_id": player.id,
                "player_name": _normalize_player_name(player.name),
                "position": player.position,
                "adp": round(adp, 2),
                "projected_points": round(projected_points, 2),
                "value_score": round(value_score, 4),
            }
        )

    return {
        "rows": rows,
        "meta": _analytics_meta(
            db,
            metric="draft_value_analysis",
            league_id=league_id,
            season=resolved_season,
        ),
    }


@router.get('/league/{league_id}/post-draft-outlook', response_model=PostDraftOutlookResponse)
def get_post_draft_outlook(
    league_id: int,
    owner_id: int | None = Query(None, ge=1),
    season: int = Query(None, description="Season year (defaults to current year)"),
    db: Session = Depends(get_db),
):
    resolved_season = _resolved_season(season)

    try:
        team_rows, owner_focus, diagnostics = build_post_draft_outlook(
            db,
            league_id=league_id,
            season=resolved_season,
            owner_id=owner_id,
        )
    except ValueError as exc:
        detail = str(exc)
        not_found_errors = {
            "League not found",
            "Owner not found in this league",
        }
        if detail in not_found_errors:
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc

    ranked_rows: list[dict] = []
    focus_payload: dict | None = None
    for idx, row in enumerate(team_rows, start=1):
        serialized = {
            "owner_id": row.owner_id,
            "owner_name": row.owner_name,
            "team_name": row.team_name,
            "rank": idx,
            "roster_size": row.roster_size,
            "projected_points": row.projected_points,
            "projected_points_vs_league_avg": row.projected_points_vs_league_avg,
            "risk_score": row.risk_score,
            "positional_balance_score": row.positional_balance_score,
            "strength_score": row.strength_score,
            "confidence_score": row.confidence_score,
            "confidence_label": row.confidence_label,
        }
        ranked_rows.append(serialized)

        if owner_focus is not None and owner_focus.owner_id == row.owner_id:
            if diagnostics.degraded_mode:
                summary = (
                    f"Rank {idx}. Data quality is degraded ({', '.join(diagnostics.degradation_reasons)}); "
                    "treat recommendations as conservative baseline guidance."
                )
            elif owner_focus.positional_gaps:
                summary = (
                    f"Rank {idx}. Focus next on {', '.join(owner_focus.positional_gaps)} "
                    "to reduce structural roster risk."
                )
            else:
                summary = f"Rank {idx}. Positional baseline is stable; prioritize upside and injury hedging."

            focus_payload = {
                "owner_id": owner_focus.owner_id,
                "rank": idx,
                "projected_points": owner_focus.projected_points,
                "projected_points_vs_league_avg": owner_focus.projected_points_vs_league_avg,
                "risk_score": owner_focus.risk_score,
                "confidence_score": owner_focus.confidence_score,
                "confidence_label": owner_focus.confidence_label,
                "positional_gaps": owner_focus.positional_gaps,
                "summary": summary,
            }

    payload = {
        "season": resolved_season,
        "team_rows": ranked_rows,
        "owner_focus": focus_payload,
        "meta": _analytics_meta(
            db,
            metric="post_draft_season_outlook",
            league_id=league_id,
            season=resolved_season,
        ),
    }

    payload["meta"]["degraded_mode"] = diagnostics.degraded_mode
    payload["meta"]["degradation_reasons"] = diagnostics.degradation_reasons
    payload["meta"]["data_quality"] = {
        "total_draft_rows": diagnostics.total_draft_rows,
        "included_rows": diagnostics.included_rows,
        "skipped_rows": diagnostics.skipped_rows,
        "duplicate_rows_skipped": diagnostics.duplicate_rows_skipped,
        "invalid_projection_rows": diagnostics.invalid_projection_rows,
        "unknown_position_rows": diagnostics.unknown_position_rows,
        "projection_coverage": diagnostics.projection_coverage,
    }
    payload["meta"]["confidence_context"] = {
        "method": "phase_b_baseline_v1",
        "model_signal_available": False,
        "simulation_signal_available": False,
        "baseline_only": True,
    }
    return payload


@router.get('/league/{league_id}/player-heatmap')
def get_player_heatmap_data(
    league_id: int,
    season: int = Query(None, description="Season year (defaults to current year)"),
    limit: int = Query(8, ge=3, le=20),
    weeks: int = Query(8, ge=4, le=17),
    db: Session = Depends(get_db),
):
    resolved_season = _resolved_season(season)

    league_player_ids = [
        row[0]
        for row in (
            db.query(models.DraftPick.player_id)
            .filter(
                models.DraftPick.league_id == league_id,
                models.DraftPick.player_id.isnot(None),
            )
            .distinct()
            .all()
        )
        if row[0] is not None
    ]

    if not league_player_ids:
        return {
            "week_labels": [],
            "rows": [],
            "meta": _analytics_meta(
                db,
                metric="player_performance_heatmap",
                league_id=league_id,
                season=resolved_season,
            ),
        }

    stats_rows = (
        db.query(
            models.PlayerWeeklyStat.player_id,
            models.PlayerWeeklyStat.week,
            sa.func.sum(models.PlayerWeeklyStat.fantasy_points).label("points"),
        )
        .filter(
            models.PlayerWeeklyStat.season == resolved_season,
            models.PlayerWeeklyStat.player_id.in_(league_player_ids),
        )
        .group_by(models.PlayerWeeklyStat.player_id, models.PlayerWeeklyStat.week)
        .order_by(models.PlayerWeeklyStat.week.asc())
        .all()
    )

    if not stats_rows:
        return {
            "week_labels": [],
            "rows": [],
            "meta": _analytics_meta(
                db,
                metric="player_performance_heatmap",
                league_id=league_id,
                season=resolved_season,
            ),
        }

    weeks_sorted = sorted({int(row.week or 0) for row in stats_rows if row.week is not None})
    weeks_used = weeks_sorted[-weeks:] if len(weeks_sorted) > weeks else weeks_sorted
    week_index = {week: idx for idx, week in enumerate(weeks_used)}

    totals_by_player: dict[int, float] = {}
    points_by_player_week: dict[int, dict[int, float]] = {}
    for row in stats_rows:
        player_id = int(row.player_id)
        week_no = int(row.week or 0)
        if week_no not in week_index:
            continue
        points = float(row.points or 0.0)
        totals_by_player[player_id] = totals_by_player.get(player_id, 0.0) + points
        points_by_player_week.setdefault(player_id, {})[week_no] = points

    top_player_ids = [
        player_id
        for player_id, _ in sorted(totals_by_player.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]

    player_rows = (
        db.query(models.Player.id, models.Player.name, models.Player.position)
        .filter(models.Player.id.in_(top_player_ids))
        .all()
    )
    player_meta = {int(row.id): row for row in player_rows}

    rows = []
    for player_id in top_player_ids:
        player = player_meta.get(int(player_id))
        if not player:
            continue
        per_week = points_by_player_week.get(int(player_id), {})
        rows.append(
            {
                "player_id": int(player.id),
                "player_name": _normalize_player_name(player.name),
                "position": player.position,
                "total_points": round(totals_by_player.get(int(player.id), 0.0), 2),
                "points_by_week": [round(per_week.get(week_no, 0.0), 2) for week_no in weeks_used],
            }
        )

    return {
        "week_labels": [f"Week {week_no}" for week_no in weeks_used],
        "rows": rows,
        "meta": _analytics_meta(
            db,
            metric="player_performance_heatmap",
            league_id=league_id,
            season=resolved_season,
        ),
    }


@router.get('/league/{league_id}/weekly-matchups')
def get_weekly_matchup_comparison(
    league_id: int,
    season: int = Query(None, description="Season year (defaults to current year)"),
    start_week: int = Query(1, ge=1, le=17),
    end_week: int = Query(17, ge=1, le=17),
    db: Session = Depends(get_db),
):
    resolved_season = _resolved_season(season)
    lower_week = min(start_week, end_week)
    upper_week = max(start_week, end_week)

    users = (
        db.query(models.User.id, models.User.team_name, models.User.username)
        .filter(models.User.league_id == league_id)
        .all()
    )
    team_name_by_id = {
        int(row.id): (row.team_name or row.username or f"Team {row.id}")
        for row in users
        if row.id is not None
    }

    matchups = (
        db.query(models.Matchup)
        .filter(
            models.Matchup.league_id == league_id,
            models.Matchup.week >= lower_week,
            models.Matchup.week <= upper_week,
        )
        .order_by(models.Matchup.week.asc(), models.Matchup.id.asc())
        .all()
    )

    by_week: dict[int, list[dict]] = {}
    for matchup in matchups:
        week_no = _safe_int(matchup.week)
        if week_no is None:
            continue

        home_id = _safe_int(matchup.home_team_id)
        away_id = _safe_int(matchup.away_team_id)
        if home_id is None or away_id is None:
            # Legacy/malformed matchup rows should not crash analytics payloads.
            continue

        entries = by_week.setdefault(week_no, [])
        entries.append(
            {
                "team_id": home_id,
                "team": team_name_by_id.get(home_id, f"Team {home_id}"),
                "score": float(matchup.home_score or 0.0),
            }
        )
        entries.append(
            {
                "team_id": away_id,
                "team": team_name_by_id.get(away_id, f"Team {away_id}"),
                "score": float(matchup.away_score or 0.0),
            }
        )

    rows = [
        {
            "week": week_no,
            "entries": sorted(entries, key=lambda row: row["score"], reverse=True),
        }
        for week_no, entries in sorted(by_week.items(), key=lambda item: item[0])
    ]

    return {
        "rows": rows,
        "meta": _analytics_meta(
            db,
            metric="weekly_matchup_comparison",
            league_id=league_id,
            season=resolved_season,
        ),
    }


@router.get('/league/{league_id}/rivalry')
def get_rivalry_graph(
    league_id: int,
    season: int = Query(None, description="Season year (ignored if matchups have no season)"),
    db: Session = Depends(get_db),
):
    """Return nodes/edges describing manager rivalries in a league.

    Edges include head-to-head games and trade counts between owners.
    """
    # collect users in the league (for node labels)
    owners = (
        db.query(models.User.id, models.User.username)
        .filter(models.User.league_id == league_id)
        .all()
    )
    nodes = [{"id": o.id, "label": o.username or f"{o.id}"} for o in owners if o.id is not None]

    # gather completed matchups
    matchup_rows = (
        db.query(models.Matchup)
        .filter(models.Matchup.league_id == league_id, models.Matchup.is_completed == True)
        .all()
    )

    # aggregate head-to-head results keyed by sorted pair
    results: dict = {}
    for m in matchup_rows:
        key = _sorted_owner_pair(m.home_team_id, m.away_team_id)
        if key is None:
            continue

        home_id = _safe_int(m.home_team_id)
        away_id = _safe_int(m.away_team_id)
        if home_id is None or away_id is None:
            continue

        if key not in results:
            results[key] = {"games": 0, "a_wins": 0, "b_wins": 0}
        results[key]["games"] += 1
        home_score = float(m.home_score or 0.0)
        away_score = float(m.away_score or 0.0)

        if home_score > away_score:
            # home wins counts toward the smaller id (a) if sorted
            if key[0] == home_id:
                results[key]["a_wins"] += 1
            else:
                results[key]["b_wins"] += 1
        elif away_score > home_score:
            if key[0] == away_id:
                results[key]["a_wins"] += 1
            else:
                results[key]["b_wins"] += 1

    # gather trade counts from transaction history
    trade_rows = (
        db.query(
            models.TransactionHistory.old_owner_id,
            models.TransactionHistory.new_owner_id,
            sa.func.count().label("cnt"),
        )
        .filter(
            models.TransactionHistory.league_id == league_id,
            models.TransactionHistory.transaction_type == "trade",
        )
        .group_by(models.TransactionHistory.old_owner_id, models.TransactionHistory.new_owner_id)
        .all()
    )
    trades: dict = {}
    for old_id, new_id, cnt in trade_rows:
        key = _sorted_owner_pair(old_id, new_id)
        if key is None:
            continue
        trades[key] = trades.get(key, 0) + cnt

    edges = []
    # include pairs from matchups
    for pair, stats in results.items():
        a, b = pair
        edges.append(
            {
                "source": a,
                "target": b,
                "games": stats["games"],
                "wins": {a: stats["a_wins"], b: stats["b_wins"]},
                "trades": trades.get(pair, 0),
            }
        )
    # include trading-only pairs
    for pair, cnt in trades.items():
        if pair not in results:
            a, b = pair
            edges.append({
                "source": a,
                "target": b,
                "games": 0,
                "wins": {a: 0, b: 0},
                "trades": cnt,
            })

    resolved_season = _resolved_season(season)
    return {
        "nodes": nodes,
        "edges": edges,
        "meta": _analytics_meta(
            db,
            metric="league_rivalry_graph",
            league_id=league_id,
            season=resolved_season,
        ),
    }


@router.get('/league/{league_id}/luck-index')
def get_luck_index(
    league_id: int,
    season: int = Query(None, description="Season year (defaults to current year)"),
    db: Session = Depends(get_db),
):
    """Calculate the 'Luck Index' — how much a manager benefited from scheduling.
    
    Returns each manager's:
    - actual_wins: real wins against actual opponents
    - hypothetical_wins: wins if manager's scores played all other schedules
    - luck: actual_wins - hypothetical_wins (positive = lucky scheduling)
    - pf: points for (scoring efficiency)
    - pa: points against (schedule strength)
    """
    resolved_season = _resolved_season(season)
    
    # Get all owners with their actual records
    owners = (
        db.query(models.User)
        .filter(
            models.User.league_id == league_id,
            models.User.is_superuser.is_(False),
            ~models.User.username.like("hist_%"),
        )
        .all()
    )
    if not owners:
        return {
            "rows": [],
            "meta": _analytics_meta(
                db,
                metric="luck_index",
                league_id=league_id,
                season=resolved_season,
            ),
        }
    
    owner_ids = {o.id for o in owners}
    owner_by_id = {o.id: o for o in owners}
    
    # Helper: get all completed matchups for an owner
    def get_owner_matchups(owner_id: int):
        return (
            db.query(models.Matchup)
            .filter(
                models.Matchup.league_id == league_id,
                or_(
                    models.Matchup.home_team_id == owner_id,
                    models.Matchup.away_team_id == owner_id,
                ),
                models.Matchup.is_completed.is_(True),
            )
            .all()
        )
    
    # Helper: calculate W-L-T from a set of matchups with owner as a specific side
    def calc_record_against(owner_id: int, matchups: list):
        w = l = t = pf = pa = 0
        for m in matchups:
            if m.home_team_id == owner_id:
                score = m.home_score or 0
                opp_score = m.away_score or 0
            else:
                score = m.away_score or 0
                opp_score = m.home_score or 0
            
            pf += score
            pa += opp_score
            if score > opp_score:
                w += 1
            elif score < opp_score:
                l += 1
            else:
                t += 1
        return w, l, t, pf, pa
    
    # Helper: calculate hypothetical record
    # For each owner, apply their scores to all other owners' opponent schedules
    def calc_hypothetical_wins(owner_id: int, owner_matchups: list, all_owners_matchups: dict):
        """
        Calculate expected wins if this owner played all other teams' schedules.
        Method: For each opponent the owner actually faced, replace with every
        other team's opponent and see cumulative wins.
        """
        total_hypothetical_w = 0
        total_hypothetical_games = 0
        
        # Get this owner's actual scores
        owner_scores = []
        for m in owner_matchups:
            if m.home_team_id == owner_id:
                owner_scores.append(m.home_score or 0)
            else:
                owner_scores.append(m.away_score or 0)
        
        # For each other owner, see what our owner's record would be against their opponents
        for other_owner_id in owner_ids:
            if other_owner_id == owner_id:
                continue
            
            other_matchups = all_owners_matchups.get(other_owner_id, [])
            if not other_matchups:
                continue
            
            # Get other owner's opponent scores (the scores this owner would face)
            hypothetical_scores = []
            for m in other_matchups:
                if m.home_team_id == other_owner_id:
                    hypothetical_scores.append(m.away_score or 0)
                else:
                    hypothetical_scores.append(m.home_score or 0)
            
            # Compare owner_scores with hypothetical_scores
            min_games = min(len(owner_scores), len(hypothetical_scores))
            for i in range(min_games):
                total_hypothetical_games += 1
                if owner_scores[i] > hypothetical_scores[i]:
                    total_hypothetical_w += 1
        
        # Average the hypothetical wins
        if total_hypothetical_games > 0:
            return round(total_hypothetical_w * len(owner_ids) / total_hypothetical_games, 1)
        return 0.0
    
    # Pre-fetch all matchups
    all_owners_matchups = {}
    for owner_id in owner_ids:
        all_owners_matchups[owner_id] = get_owner_matchups(owner_id)
    
    # Calculate luck for each owner
    rows = []
    for owner_id in owner_ids:
        matchups = all_owners_matchups[owner_id]
        if not matchups:
            continue
        
        actual_w, actual_l, actual_t, pf, pa = calc_record_against(owner_id, matchups)
        hypothetical_w = calc_hypothetical_wins(owner_id, matchups, all_owners_matchups)
        luck = round(actual_w - hypothetical_w, 1)
        
        # Calculate efficiency: fraction of total points scored (not allowed)
        total_points = pf + pa
        efficiency = round((pf / total_points) if total_points > 0 else 0.5, 3)
        
        owner = owner_by_id.get(owner_id)
        rows.append({
            "owner_id": owner_id,
            "owner_name": owner.username if owner else f"Owner {owner_id}",
            "team_name": owner.team_name if owner else f"Team {owner_id}",
            "actual_wins": actual_w,
            "actual_losses": actual_l,
            "actual_ties": actual_t,
            "actual_record": f"{actual_w}-{actual_l}" + (f"-{actual_t}" if actual_t else ""),
            "hypothetical_wins": hypothetical_w,
            "luck": luck,
            "pf": float(pf),
            "pa": float(pa),
            "efficiency": efficiency,
            "win_percentage": round((actual_w / (actual_w + actual_l)) if (actual_w + actual_l) > 0 else 0, 3),
        })
    
    # Calculate league medians for quadrant positioning
    all_pf = [r["pf"] for r in rows]
    all_pa = [r["pa"] for r in rows]
    median_pf = sorted(all_pf)[len(all_pf) // 2] if all_pf else 0
    median_pa = sorted(all_pa)[len(all_pa) // 2] if all_pa else 0
    
    # Add quadrant and luck category
    for row in rows:
        if row["pf"] >= median_pf:
            pf_quadrant = "Good"
        else:
            pf_quadrant = "Bad"
        
        if row["pa"] <= median_pa:
            pa_quadrant = "Lucky"  # Low PA = lucky (weaker opponents)
        else:
            pa_quadrant = "Unlucky"  # High PA = unlucky (stronger opponents)
        
        row["quadrant"] = f"{pf_quadrant}/{pa_quadrant}"
    
    # Sort by luck (most lucky first)
    rows.sort(key=lambda r: r["luck"], reverse=True)
    
    return {
        "rows": rows,
        "meta": _analytics_meta(
            db,
            metric="luck_index",
            league_id=league_id,
            season=resolved_season,
        ),
        "medians": {
            "pf": float(median_pf),
            "pa": float(median_pa),
        },
    }


@router.get('/league/{league_id}/player-consistency')
def get_player_consistency(
    league_id: int,
    season: int = Query(None, description="Season year (defaults to current year)"),
    limit: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
):
    """Analyze player week-to-week consistency and volatility.
    
    Returns players grouped by reliability vs volatility, with consistency metrics:
    - floor: minimum fantasy points scored in any week
    - ceiling: maximum fantasy points scored in any week
    - median: 50th percentile
    - avg: mean fantasy points
    - stdev: standard deviation
    - variance: stdev²
    - reliability_score: normalized measure (1.0 = perfect consistency)
    """
    resolved_season = _resolved_season(season)
    
    # Get all players on rosters in this league
    roster_player_ids = set()
    rosters = (
        db.query(models.Roster)
        .filter(models.Roster.league_id == league_id)
        .all()
    )
    for roster in rosters:
        if roster.players_json:
            for player_id in roster.players_json.values():
                if player_id:
                    try:
                        roster_player_ids.add(int(player_id))
                    except (TypeError, ValueError):
                        pass
    
    if not roster_player_ids:
        return {
            "most_reliable": [],
            "most_volatile": [],
            "meta": _analytics_meta(
                db,
                metric="player_consistency",
                league_id=league_id,
                season=resolved_season,
            ),
        }
    
    # Fetch weekly stats for these players
    weekly_stats = (
        db.query(models.PlayerWeeklyStat)
        .filter(
            models.PlayerWeeklyStat.player_id.in_(list(roster_player_ids)),
            models.PlayerWeeklyStat.season == resolved_season,
        )
        .all()
    )
    
    # Organize by player
    stats_by_player: dict[int, list[float]] = {}
    player_info: dict[int, dict] = {}
    
    for stat in weekly_stats:
        if stat.fantasy_points is not None:
            if stat.player_id not in stats_by_player:
                stats_by_player[stat.player_id] = []
            stats_by_player[stat.player_id].append(float(stat.fantasy_points))
            
            # Capture player info
            if stat.player_id not in player_info:
                player = stat.player
                if player:
                    player_info[stat.player_id] = {
                        "name": player.full_name or f"Player {stat.player_id}",
                        "position": player.position or "N/A",
                        "player_id": stat.player_id,
                    }
    
    # Calculate consistency metrics
    consistency_rows = []
    
    for player_id, points_list in stats_by_player.items():
        if len(points_list) < 2:
            continue  # Need at least 2 data points
        
        import statistics
        
        avg = statistics.mean(points_list)
        median = statistics.median(points_list)
        stdev = statistics.stdev(points_list) if len(points_list) > 1 else 0.0
        variance = stdev ** 2
        floor = min(points_list)
        ceiling = max(points_list)
        
        # Reliability score: normalized consistency (1.0 = never varies)
        # If avg is high and stdev is low, reliability is high
        reliability_score = avg / (avg + stdev) if (avg + stdev) > 0 else 0.5
        
        info = player_info.get(player_id, {})
        consistency_rows.append({
            "player_id": player_id,
            "player_name": info.get("name", f"Player {player_id}"),
            "position": info.get("position", "N/A"),
            "avg": round(avg, 2),
            "floor": round(floor, 2),
            "ceiling": round(ceiling, 2),
            "median": round(median, 2),
            "stdev": round(stdev, 2),
            "variance": round(variance, 2),
            "reliability_score": round(reliability_score, 3),
            "weeks_played": len(points_list),
            "weekly_points": [round(p, 2) for p in points_list],
        })
    
    # Sort by reliability (highest first) and volatility (highest stdev first)
    most_reliable = sorted(
        consistency_rows,
        key=lambda r: (-r["reliability_score"], -r["avg"]),
    )[:limit]
    
    most_volatile = sorted(
        consistency_rows,
        key=lambda r: (-r["variance"], -r["avg"]),
    )[:limit]
    
    return {
        "most_reliable": most_reliable,
        "most_volatile": most_volatile,
        "meta": _analytics_meta(
            db,
            metric="player_consistency",
            league_id=league_id,
            season=resolved_season,
        ),
    }
