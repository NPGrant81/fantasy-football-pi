from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.security import get_current_user, check_is_commissioner
from database import get_db
import models

router = APIRouter(prefix="/trades", tags=["Trades"])


class TradeProposalCreate(BaseModel):
    to_user_id: int
    offered_player_id: int
    requested_player_id: int
    note: str | None = None


@router.post("/propose")
def propose_trade(
    payload: TradeProposalCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.league_id:
        raise HTTPException(status_code=400, detail="You must be in a league to propose a trade.")

    if payload.to_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot propose a trade to yourself.")

    target_user = db.query(models.User).filter(models.User.id == payload.to_user_id).first()
    if not target_user or target_user.league_id != current_user.league_id:
        raise HTTPException(status_code=404, detail="Target manager not found in your league.")

    offered_pick = (
        db.query(models.DraftPick)
        .filter(
            models.DraftPick.owner_id == current_user.id,
            models.DraftPick.player_id == payload.offered_player_id,
            models.DraftPick.league_id == current_user.league_id,
        )
        .first()
    )
    if not offered_pick:
        raise HTTPException(status_code=400, detail="Offered player is not on your roster.")

    requested_pick = (
        db.query(models.DraftPick)
        .filter(
            models.DraftPick.owner_id == payload.to_user_id,
            models.DraftPick.player_id == payload.requested_player_id,
            models.DraftPick.league_id == current_user.league_id,
        )
        .first()
    )
    if not requested_pick:
        raise HTTPException(status_code=400, detail="Requested player is not on that manager's roster.")

    proposal = models.TradeProposal(
        league_id=current_user.league_id,
        from_user_id=current_user.id,
        to_user_id=payload.to_user_id,
        offered_player_id=payload.offered_player_id,
        requested_player_id=payload.requested_player_id,
        note=(payload.note or "").strip() or None,
        status="PENDING",
        created_at=datetime.utcnow().isoformat(),
    )

    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    return {"message": "Trade proposal submitted.", "trade_id": proposal.id}


@router.get("/pending")
def get_pending_trades(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    if not current_user.league_id:
        return []

    proposals = (
        db.query(models.TradeProposal)
        .filter(
            models.TradeProposal.league_id == current_user.league_id,
            models.TradeProposal.status == "PENDING",
        )
        .order_by(models.TradeProposal.id.desc())
        .all()
    )

    users = {u.id: u for u in db.query(models.User).filter(models.User.league_id == current_user.league_id).all()}
    allowed_positions = {"QB", "RB", "WR", "TE", "K", "DEF"}
    players = {p.id: p for p in db.query(models.Player).filter(models.Player.position.in_(allowed_positions)).all()}

    rows = []
    for trade in proposals:
        from_user = users.get(trade.from_user_id)
        to_user = users.get(trade.to_user_id)
        offered = players.get(trade.offered_player_id)
        requested = players.get(trade.requested_player_id)
        rows.append(
            {
                "id": trade.id,
                "from_user": from_user.username if from_user else "Unknown",
                "to_user": to_user.username if to_user else "Unknown",
                "players": [
                    {"name": f"Offer: {offered.name}" if offered else "Offer: Unknown"},
                    {"name": f"Request: {requested.name}" if requested else "Request: Unknown"},
                ],
                "note": trade.note,
                "status": trade.status,
                "created_at": trade.created_at,
            }
        )

    return rows
