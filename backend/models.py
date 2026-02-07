from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from database import Base

# --- 1. LEAGUE TABLE ---
class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    
    users = relationship("User", back_populates="league")

# --- 2. USER TABLE ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    league_id = Column(Integer, ForeignKey("leagues.id")) 
    league = relationship("League", back_populates="users")

    picks = relationship("DraftPick", back_populates="owner")

# --- 3. PLAYER TABLE ---
class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    position = Column(String)
    nfl_team = Column(String)
    gsis_id = Column(String, nullable=True, unique=True)
    bye_week = Column(Integer, nullable=True)

# --- 4. DRAFT PICK TABLE (Updated with Status) ---
class DraftPick(Base):
    __tablename__ = "draft_picks"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer)
    session_id = Column(String, index=True, nullable=True)
    round_num = Column(Integer, nullable=True)
    pick_num = Column(Integer, nullable=True)
    amount = Column(Integer)
    
    # NEW: Track line-up status
    current_status = Column(String, default='BENCH') 
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    
    owner = relationship("User", back_populates="picks")
    player = relationship("Player")

# --- 5. BUDGET TABLE ---
class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    year = Column(Integer)
    total_budget = Column(Integer)

# --- 6. MATCHUP TABLE ---
class Matchup(Base):
    __tablename__ = "matchups"

    id = Column(Integer, primary_key=True, index=True)
    week = Column(Integer, index=True)
    home_team_id = Column(Integer, ForeignKey("users.id"))
    away_team_id = Column(Integer, ForeignKey("users.id"))
    
    # Actual Scores
    home_score = Column(Float, default=0.0)
    away_score = Column(Float, default=0.0)

    # Projected Scores
    home_projected = Column(Float, default=0.0)
    away_projected = Column(Float, default=0.0)
    
    is_completed = Column(Boolean, default=False)
