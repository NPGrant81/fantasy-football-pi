# backend/schemas/waiver.py
from pydantic import BaseModel
from datetime import datetime

class WaiverClaim(BaseModel):
    player_id: int
    drop_player_id: int  # Standard "Add/Drop" logic
    bid_amount: int = 0  # Support for FAAB (Free Agent Acquisition Budget)
    created_at: datetime = datetime.now()
