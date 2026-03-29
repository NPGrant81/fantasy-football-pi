from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.security import get_current_user, check_is_commissioner
from ..database import get_db
from .. import models
from ..services.validation_service import (
    validate_trade_proposal_boundary,
    validate_trade_proposal_dynamic_rules,
)
from ..services.player_service import normalize_display_name as _normalize_player_name

router = APIRouter(prefix="/trades", tags=["Trades"])


class TradeProposalCreate(BaseModel):
    to_user_id: int
    offered_player_id: int
    requested_player_id: int
    offered_dollars: float | None = 0
    requested_dollars: float | None = 0
    note: str | None = None


@router.post("/propose")
def propose_trade(
    payload: TradeProposalCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    boundary_report = validate_trade_proposal_boundary(
        {
            "to_user_id": payload.to_user_id,
            "offered_player_id": payload.offered_player_id,
            "requested_player_id": payload.requested_player_id,
            "offered_dollars": payload.offered_dollars,
            "requested_dollars": payload.requested_dollars,
            "note": payload.note,
        }
    )
    if not boundary_report.valid:
        raise HTTPException(status_code=400, detail=boundary_report.errors)

    dynamic_report = validate_trade_proposal_dynamic_rules(
        {
            "current_user_id": current_user.id,
            "to_user_id": payload.to_user_id,
            "offered_player_id": payload.offered_player_id,
            "requested_player_id": payload.requested_player_id,
            "offered_dollars": float(payload.offered_dollars or 0),
            "requested_dollars": float(payload.requested_dollars or 0),
        }
    )
    if not dynamic_report.valid:
        raise HTTPException(status_code=400, detail=dynamic_report.errors)

    if not current_user.league_id:
        raise HTTPException(status_code=400, detail="You must be in a league to propose a trade.")

    # verify future dollar availability
    offered = payload.offered_dollars or 0
    requested = payload.requested_dollars or 0
    if offered < 0 or requested < 0:
        raise HTTPException(status_code=400, detail="Dollar amounts must be non-negative.")
    if current_user.future_draft_budget < offered:
        raise HTTPException(status_code=400, detail="Insufficient future draft dollars to offer.")

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

    # ensure target budget can cover requested dollars
    target_user = db.query(models.User).filter(models.User.id == payload.to_user_id).first()
    if not target_user or target_user.league_id != current_user.league_id:
        raise HTTPException(status_code=404, detail="Target manager not found in your league.")
    if target_user.future_draft_budget < requested:
        raise HTTPException(status_code=400, detail="Target manager lacks sufficient future draft dollars.")

    proposal = models.TradeProposal(
        league_id=current_user.league_id,
        from_user_id=current_user.id,
        to_user_id=payload.to_user_id,
        offered_player_id=payload.offered_player_id,
        requested_player_id=payload.requested_player_id,
        offered_dollars=offered,
        requested_dollars=requested,
        note=(payload.note or "").strip() or None,
        status="PENDING",
        created_at=datetime.now(UTC).isoformat(),
    )

    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    return {"message": "Trade proposal submitted.", "trade_id": proposal.id}


@router.post("/{trade_id}/approve")
def approve_trade(
    trade_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    from ..services.trade_service import execute_trade
    try:
        trade = execute_trade(db, trade_id, current_user.id)
        return {"message": "Trade approved", "trade": trade.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{trade_id}/reject")
def reject_trade(
    trade_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    from ..services.trade_service import reject_trade
    try:
        trade = reject_trade(db, trade_id, current_user.id)
        return {"message": "Trade rejected", "trade": trade.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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

    users = {u.id: u for u in db.query(models.User).filter(
        models.User.league_id == current_user.league_id,
        ~models.User.username.like("hist_%"),
    ).all()}
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
                    {"name": f"Offer: {_normalize_player_name(offered.name)}" if offered else "Offer: Unknown"},
                    {"name": f"Request: {_normalize_player_name(requested.name)}" if requested else "Request: Unknown"},
                ],
                "offered_dollars": float(trade.offered_dollars or 0),
                "requested_dollars": float(trade.requested_dollars or 0),
                "note": trade.note,
                "status": trade.status,
                "created_at": trade.created_at,
            }
        )

    return rows
