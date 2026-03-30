from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models
from .notifications import NotifyService


def _send(user_ids: set[int], template_id: str, context: dict) -> int:
    sent = 0
    for user_id in sorted(user_ids):
        NotifyService.send_transactional_email(
            user_id=user_id,
            template_id=template_id,
            context=context,
        )
        sent += 1
    return sent


def notify_trade_submitted(db: Session, trade: models.Trade, *, submitting_user_id: int) -> int:
    commissioner_ids = {
        int(user_id)
        for (user_id,) in db.query(models.User.id)
        .filter(models.User.league_id == trade.league_id, models.User.is_commissioner.is_(True))
        .all()
    }
    team_ids = {int(trade.team_a_id), int(trade.team_b_id)}
    recipients = (commissioner_ids | team_ids) - {int(submitting_user_id)}
    return _send(
        recipients,
        "trade_submitted_pending_review",
        {
            "league_id": trade.league_id,
            "trade_id": trade.id,
            "team_a_id": trade.team_a_id,
            "team_b_id": trade.team_b_id,
        },
    )


def notify_trade_approved(trade: models.Trade) -> int:
    recipients = {int(trade.team_a_id), int(trade.team_b_id)}
    return _send(
        recipients,
        "trade_approved",
        {
            "league_id": trade.league_id,
            "trade_id": trade.id,
            "status": trade.status,
            "commissioner_comments": trade.commissioner_comments,
        },
    )


def notify_trade_rejected(trade: models.Trade) -> int:
    recipients = {int(trade.team_a_id), int(trade.team_b_id)}
    return _send(
        recipients,
        "trade_rejected",
        {
            "league_id": trade.league_id,
            "trade_id": trade.id,
            "status": trade.status,
            "commissioner_comments": trade.commissioner_comments,
        },
    )
