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
    owned_ids_query = db.query(models.DraftPick.player_id).filter(
        models.DraftPick.league_id == league_id
    )

    rows = db.query(models.Player).filter(
        ~models.Player.id.in_(owned_ids_query),
        models.Player.position.in_(ALLOWED_POSITIONS),
    ).limit(500).all()

    candidates = dedupe_players(rows)
    if not candidates:
        return []

    player_ids = [p.id for p in candidates if p.id is not None]
    claims_by_player: dict[int, int] = {pid: 0 for pid in player_ids}
    if player_ids:
        claim_rows = db.query(models.WaiverClaim.player_id).filter(
            models.WaiverClaim.league_id == league_id,
            models.WaiverClaim.player_id.in_(player_ids),
        ).all()
        for (pid,) in claim_rows:
            if pid is not None:
                claims_by_player[pid] = claims_by_player.get(pid, 0) + 1

    ranked = []
    for player in candidates:
        projected_points = float(player.projected_points or 0.0)
        adp_value = float(player.adp or 0.0)
        adp_component = max(0.0, 200.0 - adp_value)
        recent_claim_count = int(claims_by_player.get(player.id, 0))
        claim_component = min(25.0, recent_claim_count * 5.0)

        # Deterministic weighted ranking formula for hot pickups.
        pickup_score = round(projected_points * 0.65 + adp_component * 0.25 + claim_component * 0.10, 2)

        reasons = []
        if projected_points >= 140:
            reasons.append("High projection")
        if adp_value and adp_value <= 80:
            reasons.append("Strong ADP")
        if recent_claim_count >= 2:
            reasons.append("Waiver momentum")
        if not reasons:
            reasons.append("Roster depth")

        ranked.append(
            {
                "id": player.id,
                "name": player.name,
                "position": player.position,
                "nfl_team": player.nfl_team,
                "projected_points": projected_points,
                "adp": adp_value,
                "recent_claim_count": recent_claim_count,
                "pickup_score": pickup_score,
                "pickup_reasons": reasons[:2],
            }
        )

    ranked.sort(
        key=lambda row: (
            -row["pickup_score"],
            -row["recent_claim_count"],
            -row["projected_points"],
            row["adp"] if row["adp"] > 0 else 9999,
            row["name"] or "",
            row["id"] or 0,
        )
    )
    return ranked[: max(1, min(int(limit or 10), 25))]