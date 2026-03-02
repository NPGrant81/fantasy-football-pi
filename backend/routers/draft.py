from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import or_
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Internal Imports
from ..database import get_db
import models

# Create the router
# Note: We removed the 'prefix' so your current frontend links (/draft-history) 
# don't break. We can add /draft prefix later when we update the frontend.
router = APIRouter(tags=["Draft"])

# --- 1. WEBSOCKET CONNECTION MANAGER (KEEP THIS!) ---
# This handles the "Real Time" part (pushing updates to all owners instantly)
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()


def _parse_session_context(session_id: str) -> tuple[int | None, int | None]:
    league_id = None
    draft_year = None
    parts = (session_id or "").split("_")
    for idx, value in enumerate(parts):
        if value == "LEAGUE" and idx + 1 < len(parts):
            try:
                league_id = int(parts[idx + 1])
            except ValueError:
                league_id = None
        if value == "YEAR" and idx + 1 < len(parts):
            try:
                draft_year = int(parts[idx + 1])
            except ValueError:
                draft_year = None
    return league_id, draft_year


def _get_league_settings(db: Session, league_id: int | None):
    if not league_id:
        return None
    return (
        db.query(models.LeagueSettings)
        .filter(models.LeagueSettings.league_id == league_id)
        .first()
    )


def _get_owner_total_budget(
    db: Session,
    *,
    league_id: int | None,
    owner_id: int,
    draft_year: int,
) -> int:
    budget_row = (
        db.query(models.DraftBudget)
        .filter(
            models.DraftBudget.owner_id == owner_id,
            models.DraftBudget.year == draft_year,
            models.DraftBudget.league_id == league_id,
        )
        .first()
    )
    if budget_row and budget_row.total_budget is not None:
        return int(budget_row.total_budget)

    settings = _get_league_settings(db, league_id)
    if settings and settings.salary_cap is not None:
        return int(settings.salary_cap)
    return 200


def _get_keeper_carryover_rows(db: Session, *, league_id: int | None, draft_year: int):
    if not league_id or not draft_year:
        return []
    prior_year = draft_year - 1
    return (
        db.query(models.Keeper)
        .filter(
            models.Keeper.league_id == league_id,
            models.Keeper.season == prior_year,
            or_(
                models.Keeper.status == "locked",
                models.Keeper.approved_by_commish.is_(True),
            ),
        )
        .all()
    )


def _get_enriched_history(session_id: str, db: Session):
    picks = (
        db.query(models.DraftPick)
        .filter(models.DraftPick.session_id == session_id)
        .all()
    )

    league_id, parsed_year = _parse_session_context(session_id)
    keepers = _get_keeper_carryover_rows(db, league_id=league_id, draft_year=parsed_year)

    enriched = []
    for p in picks:
        enriched.append(
            {
                "id": p.id,
                "owner_id": p.owner_id,
                "player_id": p.player_id,
                "amount": p.amount,
                "timestamp": p.timestamp,
                "position": p.player.position if p.player else None,
                "player_name": p.player.name if p.player else None,
                "is_keeper": False,
            }
        )

    for keeper in keepers:
        enriched.append(
            {
                "id": f"keeper-{keeper.id}",
                "owner_id": keeper.owner_id,
                "player_id": keeper.player_id,
                "amount": int(keeper.keep_cost or 0),
                "timestamp": (
                    keeper.created_at.isoformat()
                    if keeper.created_at is not None
                    else None
                ),
                "position": keeper.player.position if keeper.player else None,
                "player_name": keeper.player.name if keeper.player else None,
                "is_keeper": True,
            }
        )

    return enriched

# --- 2. SCHEMAS (Moved from main.py) ---
class DraftPickCreate(BaseModel):
    owner_id: int
    player_id: int 
    amount: int
    session_id: str
    year: int | None = None

# --- 3. STANDARD ENDPOINTS (From main.py - The ones working NOW) ---


# Existing endpoint
@router.get("/draft-history")
def get_draft_history(session_id: str, db: Session = Depends(get_db)):
    return _get_enriched_history(session_id=session_id, db=db)

# --- NEW: GET /draft/history (alias for /draft-history) ---
@router.get("/draft/history")
def get_draft_history_alias(session_id: str, db: Session = Depends(get_db)):
    return _get_enriched_history(session_id=session_id, db=db)

@router.post("/draft-pick")
async def draft_player(pick: DraftPickCreate, db: Session = Depends(get_db)):
    # 1. Validation Logic
    player = db.query(models.Player).filter(models.Player.id == pick.player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    existing_pick = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == pick.player_id,
        models.DraftPick.session_id == pick.session_id
    ).first()
    
    if existing_pick:
        raise HTTPException(status_code=400, detail="Player already drafted!")

    owner = db.query(models.User).filter(models.User.id == pick.owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    if pick.amount < 1:
        raise HTTPException(status_code=400, detail="Bid amount must be at least $1")

    league = None
    if owner.league_id:
        league = db.query(models.League).filter(models.League.id == owner.league_id).first()
        if league and (league.draft_status or "PRE_DRAFT") != "COMPLETED":
            league.draft_status = "ACTIVE"

    # 2. Save to Database
    year_value = pick.year
    if year_value is None:
        settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == owner.league_id).first()
        year_value = settings.draft_year if settings and settings.draft_year else datetime.utcnow().year

    settings = _get_league_settings(db, owner.league_id)
    roster_size = int(settings.roster_size) if settings and settings.roster_size else 14

    owner_picks = (
        db.query(models.DraftPick)
        .filter(
            models.DraftPick.session_id == pick.session_id,
            models.DraftPick.owner_id == owner.id,
        )
        .all()
    )
    picks_spend = sum(int(row.amount or 0) for row in owner_picks)

    league_keepers = _get_keeper_carryover_rows(
        db,
        league_id=owner.league_id,
        draft_year=year_value,
    )
    keeper_player_ids = {entry.player_id for entry in league_keepers}
    if pick.player_id in keeper_player_ids:
        raise HTTPException(
            status_code=400,
            detail="Player is already locked as a prior-season keeper",
        )

    owner_keeper_rows = [entry for entry in league_keepers if entry.owner_id == owner.id]
    keeper_spend = sum(int(entry.keep_cost or 0) for entry in owner_keeper_rows)

    owner_total_budget = _get_owner_total_budget(
        db,
        league_id=owner.league_id,
        owner_id=owner.id,
        draft_year=year_value,
    )

    total_filled_slots = len(owner_picks) + len(owner_keeper_rows)
    if total_filled_slots >= roster_size:
        raise HTTPException(status_code=400, detail="Owner roster is full")

    remaining_budget = owner_total_budget - picks_spend - keeper_spend
    empty_spots = roster_size - total_filled_slots
    max_bid = remaining_budget - (empty_spots - 1) if empty_spots > 0 else 0

    if pick.amount > max_bid:
        raise HTTPException(
            status_code=400,
            detail=f"Bid exceeds max allowed (${max(0, max_bid)})",
        )

    new_pick = models.DraftPick(
        player_id=pick.player_id,
        owner_id=pick.owner_id,
        year=year_value,
        amount=pick.amount,
        session_id=pick.session_id,
        league_id=owner.league_id,
        timestamp=datetime.utcnow().isoformat()
    )
    db.add(new_pick)
    db.commit()
    db.refresh(new_pick)

    # 3. REAL-TIME MAGIC (The new addition!)
    # Notify all connected users that a pick was made!
    await manager.broadcast({
        "event": "PICK_MADE",
        "player_id": pick.player_id,
        "owner_id": pick.owner_id,
        "amount": pick.amount,
        "player_name": player.name # useful for the ticker
    })

    return new_pick

# --- NEW: POST /draft/pick (alias for /draft-pick) ---
@router.post("/draft/pick")
async def draft_player_alias(pick: DraftPickCreate, db: Session = Depends(get_db)):
    return await draft_player(pick, db)

# --- 4. FUTURE ENDPOINTS (Auction / State) ---

@router.get("/draft/state/{league_id}")
def get_draft_state(league_id: int, db: Session = Depends(get_db)):
    return {"status": "active", "league_id": league_id}

# --- 5. THE WEBSOCKET ENDPOINT ---
@router.websocket("/ws/{league_id}")
async def websocket_endpoint(websocket: WebSocket, league_id: int):
    await manager.connect(websocket)
    try:
        while True:
            # tailored to wait for messages if you add chat later
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
