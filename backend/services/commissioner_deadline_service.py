from __future__ import annotations

import logging
from datetime import datetime

from fastapi import HTTPException

logger = logging.getLogger("fantasy")


def parse_commissioner_deadline(deadline_value: str | None) -> datetime | None:
    """Parse ISO deadline string, enforcing explicit timezone for deterministic behavior.

    Requires timezone offset (e.g., "2026-04-01T18:00:00+00:00" or "2026-04-01T18:00:00Z").
    Naive timestamps (without offset) are rejected to prevent host-local timezone ambiguity.
    """
    if not deadline_value:
        return None

    raw_deadline = deadline_value.strip()
    if not raw_deadline:
        return None

    # Normalize Z suffix to +00:00 for fromisoformat compatibility
    normalized = raw_deadline.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized)
        # Reject naive datetimes (those without timezone info)
        if parsed.tzinfo is None:
            logger.warning(
                "commissioner deadline rejected: naive timestamp detected",
                extra={"deadline_value": deadline_value},
            )
            return None
        return parsed
    except ValueError:
        return None


def enforce_commissioner_deadline(
    *,
    deadline_value: str | None,
    closed_message_prefix: str,
    now: datetime | None = None,
) -> None:
    parsed_deadline = parse_commissioner_deadline(deadline_value)
    if parsed_deadline is None:
        if deadline_value and deadline_value.strip():
            logger.warning(
                "commissioner deadline parse bypass",
                extra={"deadline_value": deadline_value, "rule": closed_message_prefix},
            )
        return

    current_time = now
    if current_time is None:
        current_time = datetime.now(parsed_deadline.tzinfo) if parsed_deadline.tzinfo else datetime.now()

    if current_time > parsed_deadline:
        raise HTTPException(
            status_code=400,
            detail=f"{closed_message_prefix} (deadline: {deadline_value}).",
        )
