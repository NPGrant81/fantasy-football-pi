from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .. import models


def record_trade_event(
    db: Session,
    *,
    trade_id: int,
    event_type: str,
    actor_user_id: int | None,
    comment: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> models.TradeEvent:
    event = models.TradeEvent(
        trade_id=trade_id,
        event_type=(event_type or "").strip().upper(),
        actor_user_id=actor_user_id,
        comment=(comment or "").strip() or None,
        metadata_json=metadata_json,
    )
    db.add(event)
    return event
