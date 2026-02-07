from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from database import Base

# --- 1. NEW: The League Table ---
class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    
    # A league has many users (owners)
    users = relationship("User", back_populates="league")
    # A league has many settings (future proofing)
    # settings = relationship("LeagueSettings", back_populates="league")

# --- 2. UPDATED: Users now belong to a League ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    # Foreign Key to League
    league_id = Column(Integer, ForeignKey("leagues.id")) 
    league = relationship("League", back_populates="users")

    # Relationships
    picks = relationship("DraftPick", back_populates="owner")

# --- 3. EXISTING: Players (Unchanged) ---
class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    position = Column(String)
    nfl_team = Column(String)
    gsis_id = Column(String, nullable=True, unique=True)
    # New: Bye Week (Story 2.1 Prep)
    bye_week = Column(Integer, nullable=True)

# --- 4. EXISTING: Draft Picks (Unchanged) ---
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