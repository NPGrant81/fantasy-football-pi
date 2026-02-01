from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)  # Matches OwnerID
    username = Column(String, unique=True, index=True)
    email = Column(String)
    
    # Relationships
    draft_picks = relationship("DraftPick", back_populates="owner")
    budgets = relationship("Budget", back_populates="owner")

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True) # Matches Player_ID
    name = Column(String, index=True)
    position = Column(String)  # Stored as "QB", "WR" (converted from 8002)
    nfl_team = Column(String)  # Stored as "ARI", "CIN" (converted from 9001)
    active = Column(Boolean, default=True)
    
    # Relationships
    draft_picks = relationship("DraftPick", back_populates="player")

class DraftPick(Base):
    __tablename__ = "draft_picks"
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer)
    round = Column(Integer, nullable=True) # Optional if data doesn't have it
    pick_num = Column(Integer, nullable=True)
    amount = Column(Float) # The WinningBid
    
    player_id = Column(Integer, ForeignKey("players.id"))
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    player = relationship("Player", back_populates="draft_picks")
    owner = relationship("User", back_populates="draft_picks")

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer)
    total_budget = Column(Float)
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="budgets")