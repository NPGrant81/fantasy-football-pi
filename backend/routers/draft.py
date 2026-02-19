from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Internal Imports
from database import get_db
import models
from core.security import get_current_user, check_is_commissioner 

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

# --- 2. SCHEMAS (Moved from main.py) ---
class DraftPickCreate(BaseModel):
    owner_id: int
    player_id: int 
    amount: int
    session_id: str

# --- 3. STANDARD ENDPOINTS (From main.py - The ones working NOW) ---


# Existing endpoint
@router.get("/draft-history")
def get_draft_history(session_id: str, db: Session = Depends(get_db)):
    return db.query(models.DraftPick).filter(models.DraftPick.session_id == session_id).all()

# --- NEW: GET /draft/history (alias for /draft-history) ---
@router.get("/draft/history")
def get_draft_history_alias(session_id: str, db: Session = Depends(get_db)):
    return db.query(models.DraftPick).filter(models.DraftPick.session_id == session_id).all()

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

    # 2. Save to Database
    new_pick = models.DraftPick(
        player_id=pick.player_id,
        owner_id=pick.owner_id,
        year=2026,
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
