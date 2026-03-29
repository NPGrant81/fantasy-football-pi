"""
consensus_service.py
--------------------
Reads per-source raw projections from ``platform_projections`` and aggregates
them into consensus ``draft_values`` rows.

This is the glue step between ETL ingestion and the Draft Day Analyzer:

    extract_espn / extract_yahoo / extract_draftsharks
            ↓  load_normalized_source_to_db
      platform_projections   (one row per player × source × season)
            ↓  build_and_store_consensus_draft_values  (this module)
         draft_values         (one consensus row per player × season)
            ↓
      draft_rankings_service.get_historical_rankings()
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Tier assignment helper
# ---------------------------------------------------------------------------

def _assign_tier(auction_value: float) -> str:
    if auction_value >= 45:
        return "S"
    if auction_value >= 30:
        return "A"
    if auction_value >= 18:
        return "B"
    if auction_value >= 8:
        return "C"
    return "D"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_and_store_consensus_draft_values(
    session: Session,
    season: int,
) -> dict[str, Any]:
    """
    Aggregate ``PlatformProjection`` rows for *season* into ``DraftValue``
    consensus records.

    Strategy per player:
    - ``avg_auction_value``  — mean auction value across all sources that
                               reported one.
    - ``median_adp``         — median ADP across sources.
    - ``value_over_replacement`` — max(0, avg_auction_value − position
                                   replacement threshold).  Replacement is the
                                   60th-percentile auction value for the same
                                   position bucket, meaning the bottom edge of
                                   the ''useful'' tier for that position.
    - ``consensus_tier``     — derived from avg_auction_value bands.
    - ``last_updated``       — UTC timestamp of this run.

    Only players that have at least one non-null auction value OR a non-zero
    ADP contributed by any source are written.  Players with no signal are
    skipped cleanly so they continue to fall through to the fallback path in
    ``draft_rankings_service``.

    Returns a summary dict:
        { "season": int, "updated": int, "skipped": int, "sources_seen": list }
    """
    from backend.models_draft_value import DraftValue, PlatformProjection

    sources_seen: set[str] = set()

    # ── Step 1: stream minimal columns and group by player_id ─────────────
    # Use batched iteration to avoid loading all ORM objects into memory.
    projection_rows = (
        session.query(
            PlatformProjection.player_id,
            PlatformProjection.source,
            PlatformProjection.auction_value,
            PlatformProjection.adp,
            PlatformProjection.projected_points,
        )
        .filter(PlatformProjection.season == season)
        .yield_per(1000)
    )

    by_player: dict[int, dict[str, list[float]]] = defaultdict(
        lambda: {"auction_values": [], "adp_values": [], "projected_points": []}
    )
    saw_projection_rows = False
    for row in projection_rows:
        saw_projection_rows = True
        if row.player_id is None:
            continue

        player_id = int(row.player_id)
        if row.source:
            sources_seen.add(row.source)

        if row.auction_value is not None:
            by_player[player_id]["auction_values"].append(float(row.auction_value))

        if row.adp is not None:
            adp = float(row.adp)
            if adp > 0:
                by_player[player_id]["adp_values"].append(adp)

        if row.projected_points is not None:
            projected = float(row.projected_points)
            if projected > 0:
                by_player[player_id]["projected_points"].append(projected)

    if not saw_projection_rows:
        return {
            "season": season,
            "updated": 0,
            "skipped": 0,
            "sources_seen": [],
            "message": f"No platform projections found for season {season}.",
        }

    # ── Step 2: resolve player positions (needed for VOR) ─────────────────
    from backend.models import Player

    player_ids = list(by_player.keys())
    player_rows = (
        session.query(Player.id, Player.position)
        .filter(Player.id.in_(player_ids))
        .all()
    )
    position_by_player: dict[int, str] = {
        int(row.id): (row.position or "UNK").upper()
        for row in player_rows
    }

    # ── Step 3: aggregate per player ──────────────────────────────────────
    aggregated: dict[int, dict[str, Any]] = {}
    for player_id, values in by_player.items():
        auction_values = values["auction_values"]
        adp_values = values["adp_values"]
        projected_points = values["projected_points"]

        if not auction_values and not adp_values and not projected_points:
            continue  # no usable signal → skip, let fallback handle it

        if auction_values:
            avg_auction = sum(auction_values) / len(auction_values)
        elif projected_points:
            # Convert projected points to an auction proxy so projected-only feeds
            # can still contribute to consensus draft values.
            avg_projected_points = sum(projected_points) / len(projected_points)
            avg_auction = max(1.0, avg_projected_points * 0.11)
        elif adp_values:
            # ADP-only feeds should still produce player-specific auction signals
            # rather than a flat default across all players.
            median_adp_for_value = statistics.median(adp_values)
            avg_auction = max(1.0, 60.0 / (1.0 + (median_adp_for_value / 12.0)))
        else:
            avg_auction = 0.0

        median_adp = statistics.median(adp_values) if adp_values else None

        aggregated[player_id] = {
            "avg_auction_value": round(avg_auction, 2),
            "median_adp": round(median_adp, 2) if median_adp is not None else None,
            "position": position_by_player.get(player_id, "UNK"),
        }

    if not aggregated:
        return {
            "season": season,
            "updated": 0,
            "skipped": len(by_player),
            "sources_seen": sorted(sources_seen),
            "message": "All players lacked usable auction/ADP values.",
        }

    # ── Step 4: compute per-position replacement threshold ────────────────
    position_buckets: dict[str, list[float]] = defaultdict(list)
    for data in aggregated.values():
        pos = data["position"]
        val = data["avg_auction_value"]
        if val > 0:
            position_buckets[pos].append(val)

    replacement_by_pos: dict[str, float] = {}
    for pos, vals in position_buckets.items():
        sorted_vals = sorted(vals, reverse=True)
        # 60th percentile from the top = bottom of the productive range
        idx = min(len(sorted_vals) - 1, max(0, int(len(sorted_vals) * 0.60)))
        replacement_by_pos[pos] = sorted_vals[idx]

    # ── Step 5: upsert into DraftValue ────────────────────────────────────
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = 0
    skipped = len(by_player) - len(aggregated)

    existing_rows = (
        session.query(DraftValue)
        .filter(DraftValue.season == season)
        .all()
    )
    existing_by_player: dict[int, DraftValue] = {
        int(row.player_id): row for row in existing_rows if row.player_id is not None
    }

    for player_id, data in aggregated.items():
        avg_auction = data["avg_auction_value"]
        pos = data["position"]
        replacement = replacement_by_pos.get(pos, 0.0)
        vor = round(max(0.0, avg_auction - replacement), 2)

        existing = existing_by_player.get(int(player_id))
        if existing is None:
            existing = DraftValue(player_id=player_id, season=season)
            session.add(existing)
            existing_by_player[int(player_id)] = existing

        existing.avg_auction_value = avg_auction
        existing.median_adp = data["median_adp"]
        existing.value_over_replacement = vor
        existing.consensus_tier = _assign_tier(avg_auction)
        existing.last_updated = now_iso
        updated += 1

    session.commit()

    return {
        "season": season,
        "updated": updated,
        "skipped": skipped,
        "sources_seen": sorted(sources_seen),
    }
