"""Resolve the configured season consistently for active financial operations."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend import models


def active_season(db: Session, league_id: int) -> int:
    settings = (
        db.query(models.LeagueSettings)
        .filter(models.LeagueSettings.league_id == league_id)
        .first()
    )
    if settings and settings.draft_year is not None:
        return int(settings.draft_year)
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if league and league.current_season is not None:
        return int(league.current_season)
    return datetime.now(UTC).year
