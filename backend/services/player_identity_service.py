from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from .. import models


def current_season(default: int | None = None) -> int:
    if default is not None:
        return int(default)
    return int(datetime.now(timezone.utc).year)


def upsert_player_season(
    db: Session,
    *,
    player_id: int,
    season: int,
    nfl_team: str | None,
    position: str | None,
    bye_week: int | None,
    is_active: bool = True,
    source: str = "sync",
) -> models.PlayerSeason:
    row = (
        db.query(models.PlayerSeason)
        .filter(
            models.PlayerSeason.player_id == int(player_id),
            models.PlayerSeason.season == int(season),
        )
        .first()
    )

    if row is None:
        row = models.PlayerSeason(
            player_id=int(player_id),
            season=int(season),
            nfl_team=nfl_team,
            position=position,
            bye_week=bye_week,
            is_active=bool(is_active),
            source=source,
        )
        db.add(row)
        return row

    row.nfl_team = nfl_team
    row.position = position
    row.bye_week = bye_week
    row.is_active = bool(is_active)
    row.source = source
    return row


def ensure_player_alias(
    db: Session,
    *,
    player_id: int,
    alias_name: str,
    source: str,
    is_primary: bool = False,
) -> models.PlayerAlias | None:
    cleaned = (alias_name or "").strip()
    if not cleaned:
        return None

    row = (
        db.query(models.PlayerAlias)
        .filter(
            models.PlayerAlias.player_id == int(player_id),
            models.PlayerAlias.alias_name == cleaned,
            models.PlayerAlias.source == source,
        )
        .first()
    )

    if row is None:
        row = models.PlayerAlias(
            player_id=int(player_id),
            alias_name=cleaned,
            source=source,
            is_primary=bool(is_primary),
        )
        db.add(row)
        return row

    if is_primary and not row.is_primary:
        row.is_primary = True
    return row


def ensure_primary_alias(db: Session, *, player_id: int, player_name: str) -> None:
    ensure_player_alias(
        db,
        player_id=player_id,
        alias_name=player_name,
        source="canonical",
        is_primary=True,
    )
