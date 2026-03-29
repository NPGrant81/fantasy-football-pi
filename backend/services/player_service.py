# backend/services/player_service.py
import re
from datetime import datetime
from collections import defaultdict

from sqlalchemy import and_, exists, func, or_
from sqlalchemy.orm import Session
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

PLACEHOLDER_NAME_PREFIXES = ("generic", "unknown", "placeholder", "test")
PLACEHOLDER_TEAM_CODES = {"", "UAT", "TEST", "MOCK", "FAKE", "TBD", "N/A"}
NAME_SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}


def _canonical_team(team: str | None) -> str:
    value = (team or "").strip().upper()
    return TEAM_ALIASES.get(value, value)


def _normalized_name(name: str | None) -> str:
    return (name or "").strip().lower().replace(".", "")


def _dedupe_normalized_name(name: str | None) -> str:
    # Collapse punctuation and suffix variants (e.g. "Chris Godwin Jr.").
    display_name = normalize_display_name(name)
    raw = (display_name or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", raw)
    tokens = [token for token in normalized.split(" ") if token]
    if tokens and tokens[-1] in NAME_SUFFIX_TOKENS:
        tokens = tokens[:-1]

    # Collapse leading initial tokens so "A.J. Brown" and "AJ Brown" align.
    if len(tokens) >= 2:
        idx = 0
        while idx < len(tokens) and len(tokens[idx]) == 1:
            idx += 1
        if idx >= 2:
            tokens = ["".join(tokens[:idx])] + tokens[idx:]

    return " ".join(tokens)


def is_placeholder_player_name(name: str | None) -> bool:
    normalized = _normalized_name(name)
    if not normalized:
        return True
    return normalized.startswith(PLACEHOLDER_NAME_PREFIXES)


def is_valid_fantasy_player(
    *,
    name: str | None,
    position: str | None,
    nfl_team: str | None,
) -> bool:
    normalized_position = (position or "").strip().upper()
    canonical_team = _canonical_team(nfl_team)
    if normalized_position not in ALLOWED_POSITIONS:
        return False
    if is_placeholder_player_name(name):
        return False
    if canonical_team in PLACEHOLDER_TEAM_CODES:
        return False
    if not canonical_team:
        return False
    return True


def is_valid_player_row(player: models.Player) -> bool:
    return is_valid_fantasy_player(
        name=player.name,
        position=player.position,
        nfl_team=player.nfl_team,
    )


def normalize_display_name(name: str | None) -> str:
    """Normalize a player name for UI display.

    - Converts MFL-import "Last, First" format to "First Last"
    - Title-cases names that are entirely lowercase
    """
    if not name:
        return ""
    result = name.strip()
    # Reorder "Last, First" → "First Last"
    if "," in result:
        parts = result.split(",", 1)
        result = f"{parts[1].strip()} {parts[0].strip()}"
    # Title-case names stored in all-lowercase
    if result == result.lower():
        result = result.title()
    return result
def canonical_player_identity(name: str | None, position: str | None, nfl_team: str | None) -> tuple[str, str, str]:
    return (
        _normalized_name(name),
        (position or "").strip().upper(),
        _canonical_team(nfl_team),
    )


def find_existing_player(
    db: Session,
    *,
    gsis_id: str | None = None,
    espn_id: str | None = None,
    name: str | None = None,
    position: str | None = None,
    nfl_team: str | None = None,
) -> models.Player | None:
    normalized_gsis_id = (gsis_id or "").strip()
    normalized_espn_id = (espn_id or "").strip()
    if normalized_gsis_id:
        existing = (
            db.query(models.Player)
            .filter(models.Player.gsis_id == normalized_gsis_id)
            .first()
        )
        if existing:
            return existing

    if normalized_espn_id:
        existing = (
            db.query(models.Player)
            .filter(models.Player.espn_id == normalized_espn_id)
            .first()
        )
        if existing:
            return existing

    identity_name, identity_position, identity_team = canonical_player_identity(
        name,
        position,
        nfl_team,
    )
    if not identity_name or not identity_position or not identity_team:
        return None

    candidates = (
        db.query(models.Player)
        .filter(models.Player.position == identity_position)
        .all()
    )
    best_match = None
    best_rank = None
    for candidate in candidates:
        if canonical_player_identity(candidate.name, candidate.position, candidate.nfl_team) != (
            identity_name,
            identity_position,
            identity_team,
        ):
            continue
        candidate_rank = _player_rank(candidate)
        if best_match is None or candidate_rank > best_rank:
            best_match = candidate
            best_rank = candidate_rank

    return best_match


def _player_dedupe_key(player: models.Player):
    # Cross-platform presentation dedupe should collapse same player identities
    # even when one row has provider IDs and another does not.
    position = (player.position or "").strip().upper()
    if position == "DEF":
        # DEF rows are frequently duplicated across legacy naming conventions
        # (e.g. "Washington Defense", "Washington Commanders").
        # Canonicalize to team+position so one team defense survives.
        return (
            "team-defense",
            position,
            _canonical_team(player.nfl_team),
        )

    return (
        "identity",
        _dedupe_normalized_name(player.name),
        position,
    )


def _player_rank(player: models.Player) -> tuple[int, int]:
    # Prefer rows with external IDs, then prefer active-team rows over FA,
    # then prefer most recently inserted IDs.
    has_external_id = 1 if (player.gsis_id or player.espn_id) else 0
    has_active_team = 1 if _canonical_team(player.nfl_team) not in {"", "FA"} else 0
    return (has_external_id, has_active_team, int(player.id or 0))


def canonical_player_key(player: models.Player):
    return _player_dedupe_key(player)


def canonical_player_rank(player: models.Player) -> tuple[int, int]:
    return _player_rank(player)


def dedupe_players(players: list[models.Player]) -> list[models.Player]:
    # Defensive first pass: guarantee unique player IDs even if upstream query
    # shape ever returns duplicate rows for the same primary key.
    selected_by_id: dict[int, models.Player] = {}
    for player in players:
        if not is_valid_player_row(player):
            continue
        player_id = int(player.id or 0)
        current_by_id = selected_by_id.get(player_id)
        if current_by_id is None or _player_rank(player) > _player_rank(current_by_id):
            selected_by_id[player_id] = player

    selected: dict[tuple, models.Player] = {}
    for player in selected_by_id.values():
        key = _player_dedupe_key(player)
        current = selected.get(key)
        if current is None or _player_rank(player) > _player_rank(current):
            selected[key] = player

    return sorted(
        selected.values(),
        key=lambda row: ((row.position or ""), (row.name or ""), int(row.id or 0)),
    )


def _active_player_or_unsynced_filter(db: Session):
    # Use data freshness from the table itself, not wall-clock year.
    current_year = datetime.now().year
    latest_synced_season = db.query(func.max(models.PlayerSeason.season)).scalar()
    anchor_season = int(latest_synced_season or current_year)
    min_recent_season = anchor_season - 1

    has_active_recent_season = exists().where(
        and_(
            models.PlayerSeason.player_id == models.Player.id,
            models.PlayerSeason.is_active.is_(True),
            models.PlayerSeason.season >= min_recent_season,
        )
    )

    has_no_season = ~exists().where(
        models.PlayerSeason.player_id == models.Player.id
    )

    inactive_teams = PLACEHOLDER_TEAM_CODES | {"FA"}
    has_unsynced_but_plausible_team = and_(
        has_no_season,
        models.Player.nfl_team.isnot(None),
        ~models.Player.nfl_team.in_(inactive_teams),
    )

    return or_(has_active_recent_season, has_unsynced_but_plausible_team)


def get_all_relevant_players(db: Session) -> list[models.Player]:
    rows = (
        db.query(models.Player)
        .filter(
            models.Player.position.in_(ALLOWED_POSITIONS),
            _active_player_or_unsynced_filter(db),
        )
        .order_by(models.Player.name, models.Player.id.desc())
        .all()
    )
    return dedupe_players(rows)


def get_player_quality_report(db: Session) -> dict[str, object]:
    current_year = datetime.now().year
    latest_synced_season = db.query(func.max(models.PlayerSeason.season)).scalar()
    anchor_season = int(latest_synced_season or current_year)
    min_recent_season = anchor_season - 1

    allowed_rows = (
        db.query(models.Player)
        .filter(models.Player.position.in_(ALLOWED_POSITIONS))
        .all()
    )
    allowed_player_ids = {int(p.id) for p in allowed_rows if p.id is not None}

    included_rows = (
        db.query(models.Player)
        .filter(
            models.Player.position.in_(ALLOWED_POSITIONS),
            _active_player_or_unsynced_filter(db),
        )
        .all()
    )

    valid_included_rows = [p for p in included_rows if is_valid_player_row(p)]
    deduped_rows = dedupe_players(included_rows)

    included_ids = {int(p.id) for p in included_rows if p.id is not None}

    recent_season_rows = (
        db.query(models.PlayerSeason.player_id, models.PlayerSeason.is_active)
        .filter(models.PlayerSeason.season >= min_recent_season)
        .all()
    )

    season_flags: dict[int, dict[str, bool]] = defaultdict(lambda: {"active": False, "inactive": False})
    for player_id, is_active in recent_season_rows:
        if player_id is None:
            continue
        pid = int(player_id)
        if is_active:
            season_flags[pid]["active"] = True
        else:
            season_flags[pid]["inactive"] = True

    any_season_ids = {
        int(row[0])
        for row in db.query(models.PlayerSeason.player_id).distinct().all()
        if row[0] is not None
    }

    active_recent_included_count = sum(
        1 for pid in included_ids if season_flags[pid]["active"]
    )
    unsynced_included_count = sum(
        1 for pid in included_ids if pid not in any_season_ids
    )

    inactive_excluded_count = sum(
        1
        for pid in allowed_player_ids
        if season_flags[pid]["inactive"] and not season_flags[pid]["active"] and pid not in included_ids
    )

    placeholder_or_invalid_filtered_count = len(included_rows) - len(valid_included_rows)
    duplicate_rows_collapsed_count = max(0, len(valid_included_rows) - len(deduped_rows))

    return {
        "season_window": {
            "anchor_season": anchor_season,
            "min_recent_season": min_recent_season,
        },
        "counts": {
            "total_allowed_position_rows": len(allowed_rows),
            "included_candidates": len(included_rows),
            "active_recent_included": active_recent_included_count,
            "unsynced_included": unsynced_included_count,
            "inactive_excluded": inactive_excluded_count,
            "placeholder_or_invalid_filtered": placeholder_or_invalid_filtered_count,
            "duplicate_rows_collapsed": duplicate_rows_collapsed_count,
            "final_deduped_players": len(deduped_rows),
        },
    }

# 1.1.1 SERVICE: Search ALL players with position filtering
def search_all_players(db: Session, query_str: str, pos: str = "ALL"):
    search_term = f"%{query_str.strip()}%"
    # Always filter to relevant positions
    query = db.query(models.Player).filter(
        models.Player.name.ilike(search_term),
        models.Player.position.in_(ALLOWED_POSITIONS),
        _active_player_or_unsynced_filter(db),
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
    """Return top available free agents ranked by projection, ADP, and waiver momentum."""
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

    momentum_by_player: dict[int, float] = {}
    claim_counts: dict[int, int] = {}

    # Use recent transaction history as the primary demand signal for pickups.
    recent_transactions = (
        db.query(
            models.TransactionHistory.player_id,
            models.TransactionHistory.transaction_type,
        )
        .filter(
            models.TransactionHistory.league_id == league_id,
            models.TransactionHistory.transaction_type.in_(["waiver_add", "waiver_drop"]),
        )
        .order_by(
            models.TransactionHistory.timestamp.desc(),
            models.TransactionHistory.id.desc(),
        )
        .limit(250)
        .all()
    )

    for player_id, transaction_type in recent_transactions:
        current = momentum_by_player.get(int(player_id), 0.0)
        if transaction_type == "waiver_add":
            momentum_by_player[int(player_id)] = current + 1.0
        elif transaction_type == "waiver_drop":
            momentum_by_player[int(player_id)] = current - 0.6

    # Waiver claims can supplement momentum in environments that persist claims.
    recent_claims = (
        db.query(models.WaiverClaim.player_id, models.WaiverClaim.status)
        .filter(models.WaiverClaim.league_id == league_id)
        .order_by(models.WaiverClaim.id.desc())
        .limit(250)
        .all()
    )

    for player_id, status in recent_claims:
        normalized_status = str(status or "").upper()
        pid = int(player_id)
        claim_counts[pid] = claim_counts.get(pid, 0) + 1
        current = momentum_by_player.get(pid, 0.0)
        if normalized_status in {"PENDING", "APPROVED", "SUCCESS"}:
            momentum_by_player[pid] = current + 0.8
        elif normalized_status in {"REJECTED", "FAILED", "CANCELLED"}:
            momentum_by_player[pid] = current - 0.3

    scarcity_bonus = {
        "QB": 1.5,
        "RB": 3.0,
        "WR": 2.5,
        "TE": 2.0,
        "K": 0.8,
        "DEF": 1.0,
    }

    scored: list[tuple[models.Player, float]] = []
    trend_meta: dict[int, tuple[float, str, int]] = {}
    for player in deduped:
        player_id = int(player.id or 0)
        projection = float(player.projected_points or 0.0)
        adp_value = float(player.adp) if player.adp is not None else 999.0
        normalized_adp = adp_value if adp_value > 0 else 999.0
        adp_signal = max(0.0, 250.0 - min(normalized_adp, 250.0)) / 25.0
        position_signal = scarcity_bonus.get((player.position or "").upper(), 1.0)
        raw_momentum = float(momentum_by_player.get(player_id, 0.0))
        trend_signal = max(-2.0, min(4.0, raw_momentum * 0.6))

        if trend_signal >= 1.2:
            trend_label = "Rising"
        elif trend_signal <= -0.5:
            trend_label = "Cooling"
        else:
            trend_label = "Steady"

        pickup_score = round(projection + adp_signal + position_signal + trend_signal, 2)
        trend_meta[player_id] = (
            round(trend_signal, 2),
            trend_label,
            int(claim_counts.get(player_id, 0)),
        )
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
        trend_score, trend_label, recent_claim_count = trend_meta.get(int(player.id or 0), (0.0, "Steady", 0))
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
                "name": normalize_display_name(player.name),
                "position": player.position,
                "nfl_team": player.nfl_team,
                "projected_points": float(player.projected_points or 0.0),
                "adp": float(player.adp or 0.0),
                "pickup_rank": index,
                "pickup_score": pickup_score,
                "pickup_tier": tier,
                "pickup_trend_score": float(trend_score),
                "pickup_trend_label": trend_label,
                "recent_claim_count": recent_claim_count,
                "pickup_rationale": "projection_plus_adp_plus_waiver_momentum",
            }
        )

    return payload
