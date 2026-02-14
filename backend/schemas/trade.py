# backend/schemas/trade.py
from pydantic import BaseModel
from typing import List, Optional

class TradeOffer(BaseModel):
    target_owner_id: int
    offered_player_ids: List[int]
    requested_player_ids: List[int]

class TradeReview(BaseModel):
    trade_id: int
    action: str  # 'APPROVE' or 'VETO'
    commish_note: Optional[str] = None
