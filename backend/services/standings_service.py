"""
standings_service.py
--------------------
Shared standings sort-key used by both league.py (owner listings) and
playoffs.py (bracket seeding) so tie-break rules stay in sync.
"""
from __future__ import annotations

from typing import Any, Dict


def owner_standings_sort_key(owner_row: Dict[str, Any]) -> tuple:
    """Return a sort tuple for a single owner stats dict.

    Sort order (ascending = better rank):
      1. Most wins (negated)
      2. Fewest losses
      3. Most ties (negated)
      4. Most points-for (negated)
      5. Fewest points-against
      6. Team/username alpha (lower-case, for determinism)
      7. Owner ID (final deterministic tiebreak)
    """
    return (
        -(owner_row.get("wins") or 0),
        owner_row.get("losses") or 0,
        -(owner_row.get("ties") or 0),
        -(owner_row.get("pf") or 0),
        owner_row.get("pa") or 0,
        (owner_row.get("team_name") or owner_row.get("username") or "").lower(),
        owner_row.get("id") or 0,
    )
