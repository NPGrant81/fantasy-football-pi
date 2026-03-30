from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..core.security import get_current_user, check_is_commissioner
from ..database import get_db
from .. import models
from ..services.validation_service import (
    validate_trade_proposal_boundary,
    validate_trade_proposal_dynamic_rules,
)
from ..services.commissioner_deadline_service import enforce_commissioner_deadline
from ..services.commissioner_deadline_service import parse_commissioner_deadline
from ..services.player_service import normalize_display_name as _normalize_player_name
from ..services.trade_validation_service import (
    TradeAssetInput,
    TradeValidationContext,
    validate_trade_request,
)
from ..services.trade_execution_service import execute_trade_v2_approval
from ..services.trade_event_service import record_trade_event

router = APIRouter(prefix="/trades", tags=["Trades"])


class TradeProposalCreate(BaseModel):
    to_user_id: int
    offered_player_id: int
    requested_player_id: int
    offered_dollars: float | None = 0
    requested_dollars: float | None = 0
    note: str | None = None


class TradeAssetCreate(BaseModel):
    asset_type: str
    player_id: int | None = None
    draft_pick_id: int | None = None
    amount: float | None = None
    season_year: int | None = None


class TradeSubmissionCreate(BaseModel):
    team_a_id: int
    team_b_id: int
    assets_from_a: list[TradeAssetCreate]
    assets_from_b: list[TradeAssetCreate]


class TradeReviewAction(BaseModel):
    commissioner_comments: str | None = None


class TradeEventOut(BaseModel):
    id: int
    trade_id: int
    event_type: str
    actor_user_id: int | None = None
    actor_username: str | None = None
    comment: str | None = None
    metadata_json: dict | None = None
    created_at: str | None = None


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

    settings = (
        db.query(models.LeagueSettings)
        .filter(models.LeagueSettings.league_id == current_user.league_id)
        .first()
    )
    enforce_commissioner_deadline(
        deadline_value=settings.trade_deadline if settings else None,
        closed_message_prefix="Trade proposals are closed by commissioner rule",
    )

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


@router.post("/leagues/{league_id}/submit-v2")
def submit_trade_v2(
    league_id: int,
    payload: TradeSubmissionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.league_id or current_user.league_id != league_id:
        raise HTTPException(status_code=403, detail="You do not have access to this league.")

    if payload.team_a_id == payload.team_b_id:
        raise HTTPException(status_code=400, detail="Trade teams must be different.")

    if current_user.id not in {payload.team_a_id, payload.team_b_id}:
        raise HTTPException(status_code=403, detail="You can only submit trades involving your own team.")

    teams = (
        db.query(models.User)
        .filter(
            models.User.id.in_([payload.team_a_id, payload.team_b_id]),
            models.User.league_id == league_id,
        )
        .all()
    )
    if len(teams) != 2:
        raise HTTPException(status_code=404, detail="Both trade teams must exist in the league.")

    settings = (
        db.query(models.LeagueSettings)
        .filter(models.LeagueSettings.league_id == league_id)
        .first()
    )
    enforce_commissioner_deadline(
        deadline_value=settings.trade_deadline if settings else None,
        closed_message_prefix="Trade proposals are closed by commissioner rule",
    )

    all_player_ids = {
        int(player_id)
        for player_id in [
            *(asset.player_id for asset in payload.assets_from_a),
            *(asset.player_id for asset in payload.assets_from_b),
        ]
        if player_id is not None
    }
    player_rows = (
        db.query(models.Player.id, models.Player.position)
        .filter(models.Player.id.in_(all_player_ids))
        .all()
    ) if all_player_ids else []
    player_positions_by_id = {int(player_id): str(position or "") for player_id, position in player_rows}

    roster_sizes_rows = (
        db.query(models.DraftPick.owner_id, func.count(models.DraftPick.id))
        .filter(
            models.DraftPick.league_id == league_id,
            models.DraftPick.owner_id.in_([payload.team_a_id, payload.team_b_id]),
            models.DraftPick.player_id.isnot(None),
        )
        .group_by(models.DraftPick.owner_id)
        .all()
    )
    roster_sizes = {int(owner_id): int(count) for owner_id, count in roster_sizes_rows}
    roster_sizes.setdefault(payload.team_a_id, 0)
    roster_sizes.setdefault(payload.team_b_id, 0)

    pick_rows = (
        db.query(models.DraftPick.id, models.DraftPick.owner_id)
        .filter(
            models.DraftPick.league_id == league_id,
            models.DraftPick.owner_id.in_([payload.team_a_id, payload.team_b_id]),
        )
        .all()
    )
    owned_pick_ids_by_team: dict[int, set[int]] = {
        payload.team_a_id: set(),
        payload.team_b_id: set(),
    }
    for pick_id, owner_id in pick_rows:
        if owner_id in owned_pick_ids_by_team:
            owned_pick_ids_by_team[int(owner_id)].add(int(pick_id))

    team_budget_map = {int(team.id): float(team.future_draft_budget or 0) for team in teams}

    assets_from_a = [
        TradeAssetInput(
            asset_type=asset.asset_type,
            player_id=asset.player_id,
            draft_pick_id=asset.draft_pick_id,
            amount=asset.amount,
            season_year=asset.season_year,
            position=player_positions_by_id.get(int(asset.player_id or 0)),
        )
        for asset in payload.assets_from_a
    ]
    assets_from_b = [
        TradeAssetInput(
            asset_type=asset.asset_type,
            player_id=asset.player_id,
            draft_pick_id=asset.draft_pick_id,
            amount=asset.amount,
            season_year=asset.season_year,
            position=player_positions_by_id.get(int(asset.player_id or 0)),
        )
        for asset in payload.assets_from_b
    ]

    current_season = (
        db.query(models.League.current_season)
        .filter(models.League.id == league_id)
        .scalar()
    )
    if current_season is None:
        current_season = datetime.now(UTC).year

    validation_report = validate_trade_request(
        TradeValidationContext(
            team_a_id=payload.team_a_id,
            team_b_id=payload.team_b_id,
            assets_from_a=assets_from_a,
            assets_from_b=assets_from_b,
            roster_sizes=roster_sizes,
            max_roster_size=int((settings.roster_size if settings else 14) or 14),
            min_roster_size=1,
            available_draft_dollars=team_budget_map,
            owned_pick_ids_by_team=owned_pick_ids_by_team,
            suppressed_positions=set(),
            player_positions_by_id=player_positions_by_id,
            trade_start_at=None,
            trade_end_at=parse_commissioner_deadline(settings.trade_deadline if settings else None),
            allow_playoff_trades=True,
            is_playoff=False,
            max_future_year_offset=2,
            current_season=int(current_season),
            now=datetime.now(UTC),
        )
    )
    if not validation_report.valid:
        raise HTTPException(status_code=400, detail=validation_report.errors)

    trade = models.Trade(
        league_id=league_id,
        team_a_id=payload.team_a_id,
        team_b_id=payload.team_b_id,
        created_by_user_id=current_user.id,
        status="PENDING",
    )
    db.add(trade)
    db.flush()

    assets: list[models.TradeAsset] = []
    for asset in payload.assets_from_a:
        assets.append(
            models.TradeAsset(
                trade_id=trade.id,
                asset_side="A",
                asset_type=(asset.asset_type or "").strip().upper(),
                player_id=asset.player_id,
                draft_pick_id=asset.draft_pick_id,
                amount=asset.amount,
                season_year=asset.season_year,
            )
        )
    for asset in payload.assets_from_b:
        assets.append(
            models.TradeAsset(
                trade_id=trade.id,
                asset_side="B",
                asset_type=(asset.asset_type or "").strip().upper(),
                player_id=asset.player_id,
                draft_pick_id=asset.draft_pick_id,
                amount=asset.amount,
                season_year=asset.season_year,
            )
        )

    if assets:
        db.add_all(assets)

    record_trade_event(
        db,
        trade_id=trade.id,
        event_type="SUBMITTED",
        actor_user_id=current_user.id,
        comment=None,
    )

    db.commit()
    db.refresh(trade)

    return {
        "message": "Trade submitted and pending commissioner review.",
        "trade_id": trade.id,
        "status": trade.status,
    }


def _serialize_trade_assets(trade: models.Trade):
    assets_from_a = []
    assets_from_b = []
    for asset in trade.assets:
        row = {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "player_id": asset.player_id,
            "player_name": _normalize_player_name(asset.player.name) if asset.player else None,
            "draft_pick_id": asset.draft_pick_id,
            "amount": float(asset.amount or 0) if asset.amount is not None else None,
            "season_year": asset.season_year,
        }
        if asset.asset_side == "A":
            assets_from_a.append(row)
        else:
            assets_from_b.append(row)
    return assets_from_a, assets_from_b


def _serialize_trade_v2(trade: models.Trade):
    assets_from_a, assets_from_b = _serialize_trade_assets(trade)
    return {
        "id": trade.id,
        "league_id": trade.league_id,
        "team_a_id": trade.team_a_id,
        "team_a_name": trade.team_a.username if trade.team_a else f"User {trade.team_a_id}",
        "team_b_id": trade.team_b_id,
        "team_b_name": trade.team_b.username if trade.team_b else f"User {trade.team_b_id}",
        "status": trade.status,
        "commissioner_comments": trade.commissioner_comments,
        "submitted_at": trade.submitted_at.isoformat() if trade.submitted_at else None,
        "approved_at": trade.approved_at.isoformat() if trade.approved_at else None,
        "rejected_at": trade.rejected_at.isoformat() if trade.rejected_at else None,
        "assets_from_a": assets_from_a,
        "assets_from_b": assets_from_b,
    }


def _serialize_trade_event(event: models.TradeEvent):
    return {
        "id": event.id,
        "trade_id": event.trade_id,
        "event_type": event.event_type,
        "actor_user_id": event.actor_user_id,
        "actor_username": event.actor_user.username if event.actor_user else None,
        "comment": event.comment,
        "metadata_json": event.metadata_json,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


@router.get("/leagues/{league_id}/pending-v2")
def get_pending_trades_v2(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    if current_user.league_id != league_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You do not have access to this league.")

    trades = (
        db.query(models.Trade)
        .filter(
            models.Trade.league_id == league_id,
            models.Trade.status == "PENDING",
        )
        .order_by(models.Trade.id.desc())
        .all()
    )
    return [_serialize_trade_v2(trade) for trade in trades]


@router.get("/leagues/{league_id}/{trade_id}-v2")
def get_trade_detail_v2(
    league_id: int,
    trade_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    if current_user.league_id != league_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You do not have access to this league.")

    trade = (
        db.query(models.Trade)
        .filter(models.Trade.id == trade_id, models.Trade.league_id == league_id)
        .first()
    )
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")
    return _serialize_trade_v2(trade)


@router.get("/leagues/{league_id}/{trade_id}/history-v2", response_model=list[TradeEventOut])
def get_trade_history_v2(
    league_id: int,
    trade_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    if current_user.league_id != league_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You do not have access to this league.")

    trade = (
        db.query(models.Trade)
        .filter(models.Trade.id == trade_id, models.Trade.league_id == league_id)
        .first()
    )
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")

    events = (
        db.query(models.TradeEvent)
        .filter(models.TradeEvent.trade_id == trade_id)
        .order_by(models.TradeEvent.created_at.asc(), models.TradeEvent.id.asc())
        .all()
    )
    return [_serialize_trade_event(event) for event in events]


@router.post("/leagues/{league_id}/{trade_id}/approve-v2")
def approve_trade_v2(
    league_id: int,
    trade_id: int,
    payload: TradeReviewAction,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    if current_user.league_id != league_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You do not have access to this league.")

    trade = (
        db.query(models.Trade)
        .filter(models.Trade.id == trade_id, models.Trade.league_id == league_id)
        .first()
    )
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")
    if trade.status != "PENDING":
        raise HTTPException(status_code=400, detail="Only pending trades can be approved.")

    try:
        trade = execute_trade_v2_approval(
            db,
            trade_id=trade.id,
            approver_id=current_user.id,
            commissioner_comments=payload.commissioner_comments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "message": "Trade approved",
        "trade": _serialize_trade_v2(trade),
    }


@router.post("/leagues/{league_id}/{trade_id}/reject-v2")
def reject_trade_v2(
    league_id: int,
    trade_id: int,
    payload: TradeReviewAction,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    if current_user.league_id != league_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You do not have access to this league.")

    trade = (
        db.query(models.Trade)
        .filter(models.Trade.id == trade_id, models.Trade.league_id == league_id)
        .first()
    )
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")
    if trade.status != "PENDING":
        raise HTTPException(status_code=400, detail="Only pending trades can be rejected.")

    trade.status = "REJECTED"
    trade.rejected_at = datetime.now(UTC)
    trade.commissioner_comments = (payload.commissioner_comments or "").strip() or None

    record_trade_event(
        db,
        trade_id=trade.id,
        event_type="REJECTED",
        actor_user_id=current_user.id,
        comment=trade.commissioner_comments,
    )

    db.commit()
    db.refresh(trade)

    return {
        "message": "Trade rejected",
        "trade": _serialize_trade_v2(trade),
    }


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
