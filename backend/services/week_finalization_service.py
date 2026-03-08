from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from .scoring_service import recalculate_league_week_scores


def _standings_snapshot(db: Session, league_id: int) -> list[dict[str, Any]]:
    owners = db.query(models.User).filter(models.User.league_id == league_id).all()
    rows: list[dict[str, Any]] = []

    for owner in owners:
        wins = losses = ties = 0
        points_for = points_against = 0.0

        matches = (
            db.query(models.Matchup)
            .filter(
                models.Matchup.league_id == league_id,
                or_(
                    models.Matchup.home_team_id == owner.id,
                    models.Matchup.away_team_id == owner.id,
                ),
                models.Matchup.is_completed.is_(True),
            )
            .all()
        )

        for matchup in matches:
            if matchup.home_team_id == owner.id:
                score = float(matchup.home_score or 0.0)
                opp = float(matchup.away_score or 0.0)
            else:
                score = float(matchup.away_score or 0.0)
                opp = float(matchup.home_score or 0.0)

            points_for += score
            points_against += opp
            if score > opp:
                wins += 1
            elif score < opp:
                losses += 1
            else:
                ties += 1

        rows.append(
            {
                "owner_id": int(owner.id),
                "team_name": owner.team_name or owner.username or f"Team {owner.id}",
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "points_for": round(points_for, 2),
                "points_against": round(points_against, 2),
            }
        )

    rows.sort(key=lambda row: (-row["wins"], -row["points_for"], row["owner_id"]))
    return rows


def finalize_league_week(
    db: Session,
    *,
    league_id: int,
    week: int,
    season: int,
    season_year: int | None = None,
) -> dict[str, Any]:
    recalculated = recalculate_league_week_scores(
        db,
        league_id=league_id,
        week=week,
        season=season,
        season_year=season_year,
    )

    # recalculate_league_week_scores marks each matchup FINAL/completed.
    db.flush()

    standings = _standings_snapshot(db, league_id)

    return {
        "league_id": int(league_id),
        "week": int(week),
        "season": int(season),
        "season_year": season_year,
        "finalized_at": datetime.now(timezone.utc).isoformat(),
        "matchups_finalized": len(recalculated),
        "matchup_results": recalculated,
        "standings": standings,
    }
