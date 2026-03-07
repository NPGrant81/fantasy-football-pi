# backend/services/player_service.py
from sqlalchemy.orm import Session
from sqlalchemy import not_
from .. import models

# Only relevant fantasy positions from active NFL rosters
ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}

TEAM_ALIASES = {
    "JAX": "JAC",
    "WSH": "WAS",
    "LA": "LAR",
    "STL": "LAR",
    "SD": "LAC",
    "OAK": "LV",
}


def _canonical_team(team: str | None) -> str:
    value = (team or "").strip().upper()
    return TEAM_ALIASES.get(value, value)


def _normalized_name(name: str | None) -> str:
    return (name or "").strip().lower().replace(".", "")


def _player_dedupe_key(player: models.Player):
    if player.gsis_id:
        return ("gsis", str(player.gsis_id).strip())
    if player.espn_id:
        return ("espn", str(player.espn_id).strip())
    return (
        "fallback",
        _normalized_name(player.name),
        (player.position or "").strip().upper(),
        _canonical_team(player.nfl_team),
    )


def _player_rank(player: models.Player) -> tuple[int, int]:
    # Prefer rows with external IDs, then prefer most recently inserted IDs.
    has_external_id = 1 if (player.gsis_id or player.espn_id) else 0
    return (has_external_id, int(player.id or 0))


def canonical_player_key(player: models.Player):
    return _player_dedupe_key(player)


def canonical_player_rank(player: models.Player) -> tuple[int, int]:
    return _player_rank(player)


def dedupe_players(players: list[models.Player]) -> list[models.Player]:
    selected: dict[tuple, models.Player] = {}
    for player in players:
        key = _player_dedupe_key(player)
        current = selected.get(key)
        if current is None or _player_rank(player) > _player_rank(current):
            selected[key] = player

    return sorted(
        selected.values(),
        key=lambda row: ((row.position or ""), (row.name or ""), int(row.id or 0)),
    )

# 1.1.1 SERVICE: Search ALL players with position filtering
def search_all_players(db: Session, query_str: str, pos: str = "ALL"):
    search_term = f"%{query_str.strip()}%"
    # Always filter to relevant positions
    query = db.query(models.Player).filter(
        models.Player.name.ilike(search_term),
        models.Player.position.in_(ALLOWED_POSITIONS)
    )
    
    if pos != "ALL":
        query = query.filter(models.Player.position == pos)
    
    rows = query.limit(60).all()
    return dedupe_players(rows)[:15]

# 1.1.2 SERVICE: Find Available Free Agents in a specific league
def get_league_free_agents(db: Session, league_id: int):
    # Subquery for IDs of all players owned in THIS league
    owned_ids_query = db.query(models.DraftPick.player_id).filter(
        models.DraftPick.league_id == league_id
    )
    
    # Return only relevant position players NOT owned in this league
    rows = db.query(models.Player).filter(
        ~models.Player.id.in_(owned_ids_query),
        models.Player.position.in_(ALLOWED_POSITIONS)
    ).limit(250).all()
    return dedupe_players(rows)[:50]