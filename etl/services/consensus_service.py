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

    projections = (
        session.query(PlatformProjection)
        .filter(PlatformProjection.season == season)
        .all()
    )

    if not projections:
        return {
            "season": season,
            "updated": 0,
            "skipped": 0,
            "sources_seen": [],
            "message": f"No platform projections found for season {season}.",
        }

    sources_seen: set[str] = set()

    # ── Step 1: group by player_id ─────────────────────────────────────────
    by_player: dict[int, list[PlatformProjection]] = defaultdict(list)
    for proj in projections:
        if proj.player_id:
            by_player[int(proj.player_id)].append(proj)
            if proj.source:
                sources_seen.add(proj.source)

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
    for player_id, rows in by_player.items():
        auction_values = [
            float(r.auction_value)
            for r in rows
            if r.auction_value is not None
        ]
        adp_values = [
            float(r.adp)
            for r in rows
            if r.adp is not None and float(r.adp) > 0
        ]

        if not auction_values and not adp_values:
            continue  # no usable signal → skip, let fallback handle it

        avg_auction = sum(auction_values) / len(auction_values) if auction_values else 0.0

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

    for player_id, data in aggregated.items():
        avg_auction = data["avg_auction_value"]
        pos = data["position"]
        replacement = replacement_by_pos.get(pos, 0.0)
        vor = round(max(0.0, avg_auction - replacement), 2)

        existing = (
            session.query(DraftValue)
            .filter(
                DraftValue.player_id == player_id,
                DraftValue.season == season,
            )
            .first()
        )
        if existing is None:
            existing = DraftValue(player_id=player_id, season=season)
            session.add(existing)

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
