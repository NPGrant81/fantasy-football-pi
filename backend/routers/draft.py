from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Dict

from database import get_db
import models
import schemas
from auth import get_current_user, get_current_league_commissioner

router = APIRouter(
    prefix="/draft",
    tags=["draft"]
)

# --- WEBSOCKET CONNECTION MANAGER ---
# This handles the "Real Time" part (pushing updates to all 12 owners instantly)
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

# --- HTTP ENDPOINTS (The Buttons) ---

# 1. GET DRAFT STATE (Is it paused? Who is on the clock?)
@router.get("/state/{league_id}")
def get_draft_state(league_id: int, db: Session = Depends(get_db)):
    # In a real app, you might store "Current Nominator" in a DraftState table.
    # For now, we return basic info.
    return {"status": "active", "league_id": league_id}

# 2. NOMINATE A PLAYER (Start the bidding)
@router.post("/nominate")
async def nominate_player(
    nomination: schemas.DraftPickCreate, # You might need to add this schema
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Logic: Validate it's this user's turn
    # Logic: Set the "Current Bid" to $1
    
    # Broadcast to everyone: "Nick nominated Josh Allen for $1"
    await manager.broadcast({
        "event": "NOMINATION",
        "player_id": nomination.player_id,
        "nominator": current_user.username,
        "amount": 1
    })
    return {"status": "nominated"}

# 3. PLACE BID
@router.post("/bid")
async def place_bid(
    bid: dict, # {amount: 5, player_id: "8002"}
    current_user: models.User = Depends(get_current_user)
):
    # Logic: Check user budget
    # Logic: Check if bid > current bid
    
    await manager.broadcast({
        "event": "NEW_BID",
        "bidder": current_user.username,
        "amount": bid["amount"]
    })
    return {"status": "accepted"}

# --- THE WEBSOCKET ENDPOINT ---
# This is what the Frontend connects to for the live ticker
@router.websocket("/ws/{league_id}")
async def websocket_endpoint(websocket: WebSocket, league_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # We can handle chat messages or "heartbeats" here
    except WebSocketDisconnect:
        manager.disconnect(websocket)
