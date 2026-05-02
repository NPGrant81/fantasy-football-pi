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


def deactivate_stale_player_seasons(
    db: Session,
    *,
    season: int,
    active_player_ids: set[int],
    min_active_threshold: int = 100,
) -> int:
    """Set ``is_active=False`` on PlayerSeason rows that were absent from the
    current sync feed.

    Only non-DEF players are considered — defense rows are never deactivated
    via feed comparison because they are not reliably present in ESPN player
    lists.  The caller must guarantee that ``active_player_ids`` is the full
    set of local ``players.id`` values seen in the feed for this season; any
    player NOT in that set and currently marked active will be deactivated.

    A minimum threshold guard prevents mass-deactivation when the upstream
    feed returns a suspiciously small payload (bad fetch / partial response).

    Returns the number of rows deactivated.
    """
    if len(active_player_ids) < min_active_threshold:
        return 0

    # Fetch all currently-active non-DEF seasons for this season year.
    stale_rows = (
        db.query(models.PlayerSeason)
        .join(models.Player, models.Player.id == models.PlayerSeason.player_id)
        .filter(
            models.PlayerSeason.season == int(season),
            models.PlayerSeason.is_active.is_(True),
            models.Player.position != "DEF",
        )
        .all()
    )

    deactivated = 0
    for row in stale_rows:
        if int(row.player_id) not in active_player_ids:
            row.is_active = False
            row.source = "nfl_daily_sync_deactivated"
            deactivated += 1

    if deactivated:
        db.flush()

    return deactivated
