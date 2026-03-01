from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import sqlalchemy as sa
from typing import List

from ..database import get_db
from .. import models
# import organizer helper from team router for roster-strength computation
from .team import organize_roster

router = APIRouter(prefix="/analytics", tags=["Analytics"])


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
    if season is None:
        from datetime import datetime
        season = datetime.now().year

    try:
        query = (
            db.query(
                models.ManagerEfficiency.manager_id,
                models.ManagerEfficiency.league_id,
                models.ManagerEfficiency.season,
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

    return [format_leaderboard_row(r) for r in rows]


@router.get('/roster-strength')
def get_roster_strength(
    league_id: int,
    owner_id: int,
    other_owner_id: int | None = None,
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
    return result


@router.get('/league/{league_id}/weekly-stats')
def get_weekly_stats(
    league_id: int,
    manager_id: int,
    season: int = Query(None),
    db: Session = Depends(get_db),
):
    if season is None:
        from datetime import datetime
        season = datetime.now().year

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

    return [
        {
            'week': r.week,
            'actual': float(r.actual_points_total),
            'max': float(r.optimal_points_total),
            'efficiency': float(r.efficiency_rating),
            'points_left': float(r.points_left_on_bench or 0),
        }
        for r in stats
    ]


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
    nodes = [{"id": o.id, "label": o.username or f"{o.id}"} for o in owners]

    # gather completed matchups
    matchup_rows = (
        db.query(models.Matchup)
        .filter(models.Matchup.league_id == league_id, models.Matchup.is_completed == True)
        .all()
    )

    # aggregate head-to-head results keyed by sorted pair
    results: dict = {}
    for m in matchup_rows:
        key = tuple(sorted([m.home_team_id, m.away_team_id]))
        if key not in results:
            results[key] = {"games": 0, "a_wins": 0, "b_wins": 0}
        results[key]["games"] += 1
        if m.home_score > m.away_score:
            # home wins counts toward the smaller id (a) if sorted
            if key[0] == m.home_team_id:
                results[key]["a_wins"] += 1
            else:
                results[key]["b_wins"] += 1
        elif m.away_score > m.home_score:
            if key[0] == m.away_team_id:
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
        key = tuple(sorted([old_id, new_id]))
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

    return {"nodes": nodes, "edges": edges}
