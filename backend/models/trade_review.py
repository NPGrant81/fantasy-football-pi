# backend/models/trade_review.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from database import Base

class TradeReview(Base):
    """
    State-machine for trades: PENDING -> APPROVED/VETOED.
    Ensures 'God Mode' control over bad-faith deals.
    """
    __tablename__ = "trade_reviews"
    id = Column(Integer, primary_key=True)
    trade_id = Column(Integer, ForeignKey("trades.id"))
    status = Column(String, default="PENDING") # PENDING, APPROVED, VETOED
    commish_note = Column(String, nullable=True) # e.g., "Vetoed: Unbalanced value/Collusion"
