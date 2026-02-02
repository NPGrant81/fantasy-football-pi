from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    picks = relationship("DraftPick", back_populates="owner")

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    position = Column(String)
    nfl_team = Column(String)
    # --- NEW: The "Anchor" ID from NFL Official Data ---
    gsis_id = Column(String, nullable=True, unique=True) 

class DraftPick(Base):
    __tablename__ = "draft_picks"
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer)
    session_id = Column(String, index=True, nullable=True)
    round_num = Column(Integer, nullable=True)
    pick_num = Column(Integer, nullable=True)
    amount = Column(Integer)
    owner_id = Column(Integer, ForeignKey("users.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    owner = relationship("User", back_populates="picks")
    player = relationship("Player")

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    year = Column(Integer)
    total_budget = Column(Integer)