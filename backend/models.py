from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, JSON, Enum as SqlEnum
from sqlalchemy.orm import relationship
from database import Base
import enum

# --- 0. ENUMS ---
class UserRole(str, enum.Enum):
    ADMIN = "admin"
    COMMISSIONER = "commissioner"
    USER = "user"

# --- 1. LEAGUE TABLE ---
class League(Base):
    __tablename__ = "leagues"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    
    users = relationship("User", back_populates="league")
    scoring_rules = relationship("ScoringRule", back_populates="league")
    settings = relationship("LeagueSettings", back_populates="league", uselist=False)
    matchups = relationship("Matchup", back_populates="league")

# --- 2. LEAGUE SETTINGS ---
class LeagueSettings(Base):
    __tablename__ = "league_settings"
    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    
    roster_size = Column(Integer, default=14)
    salary_cap = Column(Integer, default=200)
    starting_slots = Column(JSON, default={
        "QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1, "FLEX": 1
    })
    
    league = relationship("League", back_populates="settings")

# --- 3. USER TABLE (The Team Owner) ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String)
    
    is_superuser = Column(Boolean, default=False)
    is_commissioner = Column(Boolean, default=False)
    division = Column(String, nullable=True)

    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True) 
    league = relationship("League", back_populates="users") 
    
    picks = relationship("DraftPick", back_populates="owner")
    home_matches = relationship("Matchup", foreign_keys="Matchup.home_team_id", back_populates="home_team")
    away_matches = relationship("Matchup", foreign_keys="Matchup.away_team_id", back_populates="away_team")

# --- 4. PLAYER TABLE ---
class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    position = Column(String)
    nfl_team = Column(String)
    gsis_id = Column(String, nullable=True, unique=True)
    bye_week = Column(Integer, nullable=True)

# --- 5. DRAFT PICK TABLE (Your Roster) ---
class DraftPick(Base):
    __tablename__ = "draft_picks"
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer)
    round_num = Column(Integer, nullable=True)
    pick_num = Column(Integer, nullable=True)
    amount = Column(Integer) # Auction Value
    current_status = Column(String, default='BENCH') 
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    
    owner = relationship("User", back_populates="picks")
    player = relationship("Player")

# --- 6. MATCHUP TABLE ---
class Matchup(Base):
    __tablename__ = "matchups"
    id = Column(Integer, primary_key=True, index=True)
    week = Column(Integer, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True)

    home_team_id = Column(Integer, ForeignKey("users.id"))
    away_team_id = Column(Integer, ForeignKey("users.id"))
    
    home_score = Column(Float, default=0.0)
    away_score = Column(Float, default=0.0)
    is_completed = Column(Boolean, default=False)

    league = relationship("League", back_populates="matchups")
    home_team = relationship("User", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("User", foreign_keys=[away_team_id], back_populates="away_matches")

# --- 7. SCORING RULES ---
class ScoringRule(Base):
    __tablename__ = "scoring_rules"
    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    
    category = Column(String) 
    description = Column(String, nullable=True)
    min_val = Column(Float, default=0) 
    max_val = Column(Float, default=999) 
    points = Column(Float, default=0) 
    position_target = Column(String, nullable=True) 
    
    league = relationship("League", back_populates="scoring_rules")