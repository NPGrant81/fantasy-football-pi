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


def get_top_free_agents(db: Session, league_id: int, limit: int = 10):
    """Return top available free agents ranked by projection plus demand signal."""
    safe_limit = max(1, min(int(limit), 25))

    owned_ids_query = db.query(models.DraftPick.player_id).filter(
        models.DraftPick.league_id == league_id
    )

    rows = (
        db.query(models.Player)
        .filter(
            ~models.Player.id.in_(owned_ids_query),
            models.Player.position.in_(ALLOWED_POSITIONS),
        )
        .order_by(
            models.Player.projected_points.desc(),
            models.Player.adp.asc(),
            models.Player.name.asc(),
        )
        .limit(400)
        .all()
    )

    deduped = dedupe_players(rows)

    scarcity_bonus = {
        "QB": 1.5,
        "RB": 3.0,
        "WR": 2.5,
        "TE": 2.0,
        "K": 0.8,
        "DEF": 1.0,
    }

    scored: list[tuple[models.Player, float]] = []
    for player in deduped:
        projection = float(player.projected_points or 0.0)
        adp_value = float(player.adp) if player.adp is not None else 999.0
        normalized_adp = adp_value if adp_value > 0 else 999.0
        adp_signal = max(0.0, 250.0 - min(normalized_adp, 250.0)) / 25.0
        position_signal = scarcity_bonus.get((player.position or "").upper(), 1.0)
        pickup_score = round(projection + adp_signal + position_signal, 2)
        scored.append((player, pickup_score))

    ranked = sorted(
        scored,
        key=lambda row: (
            -row[1],
            -(float(row[0].projected_points or 0.0)),
            float(row[0].adp or 999999.0),
            row[0].name or "",
        ),
    )

    if not ranked:
        return []

    top_score = ranked[0][1]
    payload: list[dict] = []
    for index, (player, pickup_score) in enumerate(ranked[:safe_limit], start=1):
        ratio = (pickup_score / top_score) if top_score > 0 else 0.0
        if ratio >= 0.98:
            tier = "S"
        elif ratio >= 0.94:
            tier = "A"
        elif ratio >= 0.90:
            tier = "B"
        else:
            tier = "C"

        payload.append(
            {
                "id": player.id,
                "name": player.name,
                "position": player.position,
                "nfl_team": player.nfl_team,
                "projected_points": float(player.projected_points or 0.0),
                "adp": float(player.adp or 0.0),
                "pickup_rank": index,
                "pickup_score": pickup_score,
                "pickup_tier": tier,
                "pickup_rationale": "projection_plus_adp_signal",
            }
        )

    return payload