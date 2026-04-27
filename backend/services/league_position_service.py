from sqlalchemy.orm import Session

from .. import models


ACTIVE_PLAYER_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")


def normalize_player_position(position: str | None) -> str:
    normalized = str(position or "").strip().upper()
    if normalized == "TD":
        return "DEF"
    return normalized


def get_active_positions_for_league(db: Session, league_id: int | None) -> list[str]:
    if not league_id:
        return list(ACTIVE_PLAYER_POSITIONS)

    settings = (
        db.query(models.LeagueSettings)
        .filter(models.LeagueSettings.league_id == league_id)
        .first()
    )
    if not settings or not isinstance(settings.starting_slots, dict):
        return list(ACTIVE_PLAYER_POSITIONS)

    slots = settings.starting_slots
    if not slots:
        return list(ACTIVE_PLAYER_POSITIONS)

    has_position_config = any(
        f"MAX_{position}" in slots or position in slots
        for position in ACTIVE_PLAYER_POSITIONS
    )
    if not has_position_config:
        return list(ACTIVE_PLAYER_POSITIONS)

    active_positions: list[str] = []
    for position in ACTIVE_PLAYER_POSITIONS:
        max_key = f"MAX_{position}"
        fallback = 1 if position == "DEF" else 0
        raw_value = slots.get(max_key, slots.get(position, fallback))
        try:
            enabled = int(raw_value) > 0
        except (TypeError, ValueError):
            enabled = position == "DEF"
        if enabled:
            active_positions.append(position)

    return active_positions or list(ACTIVE_PLAYER_POSITIONS)


def is_position_allowed_for_league(
    db: Session,
    league_id: int | None,
    player_position: str | None,
) -> bool:
    normalized_position = normalize_player_position(player_position)
    if not normalized_position:
        return False
    return normalized_position in set(get_active_positions_for_league(db, league_id))