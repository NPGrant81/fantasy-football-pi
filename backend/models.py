from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, JSON
from sqlalchemy.orm import relationship
from database import Base

# --- 1. LEAGUE TABLE (The missing piece!) ---
class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    
    users = relationship("User", back_populates="league")

# --- 2. LEAGUE SETTINGS ---
class LeagueSettings(Base):
    __tablename__ = "league_settings"

    id = Column(Integer, primary_key=True, index=True)
    league_name = Column(String, default="My Fantasy League")
    
    # Roster Rules
    roster_size = Column(Integer, default=14)
    salary_cap = Column(Integer, default=200)
    
    # Starting Slots (stored as JSON)
    starting_slots = Column(JSON, default={
        "QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1, "FLEX": 1
    })
    
    # Scoring Rules (stored as JSON)
    scoring_rules = Column(JSON, default=[])

# --- 3. USER TABLE ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    # Admin Rights
    is_commissioner = Column(Boolean, default=False)

    # Relationship to League
    league_id = Column(Integer, ForeignKey("leagues.id")) 
    league = relationship("League", back_populates="users")
    
    picks = relationship("DraftPick", back_populates="owner")

# --- 4. PLAYER TABLE ---
class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    position = Column(String)
    nfl_team = Column(String)
    gsis_id = Column(String, nullable=True, unique=True)
    bye_week = Column(Integer, nullable=True)

# --- 5. DRAFT PICK TABLE ---
class DraftPick(Base):
    __tablename__ = "draft_picks"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer)
    session_id = Column(String, index=True, nullable=True)
    round_num = Column(Integer, nullable=True)
    pick_num = Column(Integer, nullable=True)
    amount = Column(Integer)
    
    # Lineup Status
    current_status = Column(String, default='BENCH') 
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    
    owner = relationship("User", back_populates="picks")
    player = relationship("Player")

# --- 6. BUDGET TABLE ---
class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    year = Column(Integer)
    total_budget = Column(Integer)

# --- 7. MATCHUP TABLE ---
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