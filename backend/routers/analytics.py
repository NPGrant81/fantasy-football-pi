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
