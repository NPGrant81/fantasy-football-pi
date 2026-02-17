from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, JSON
from sqlalchemy.orm import relationship
from database import Base

# --- 1. USER TABLE ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String)
    
    # 1.1 ROLES
    is_superuser = Column(Boolean, default=False)
    is_commissioner = Column(Boolean, default=False)
    
    # 1.2 LEAGUE INFO
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True)
    division = Column(String, nullable=True)
    team_name = Column(String, nullable=True)

    # Relationships
    league = relationship("League", back_populates="users") 
    picks = relationship("DraftPick", back_populates="owner")
    claims = relationship("WaiverClaim", back_populates="user")
    home_matches = relationship("Matchup", foreign_keys="Matchup.home_team_id", back_populates="home_team")
    away_matches = relationship("Matchup", foreign_keys="Matchup.away_team_id", back_populates="away_team")

# --- 2. LEAGUE TABLE ---
class League(Base):
    __tablename__ = "leagues"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    draft_status = Column(String, default="PRE_DRAFT") 
    created_at = Column(String, nullable=True)

    # Relationships
    users = relationship("User", back_populates="league")
    scoring_rules = relationship("ScoringRule", back_populates="league")
    settings = relationship("LeagueSettings", back_populates="league", uselist=False)
    matchups = relationship("Matchup", back_populates="league")
    draft_picks = relationship("DraftPick", back_populates="league")
    waiver_claims = relationship("WaiverClaim", back_populates="league")

# --- 3. LEAGUE SETTINGS ---
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

# --- 4. PLAYER TABLE ---
class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    position = Column(String)
    nfl_team = Column(String)
    adp = Column(Float, default=0.0)
    projected_points = Column(Float, default=0.0)
    gsis_id = Column(String, nullable=True, unique=True)
    bye_week = Column(Integer, nullable=True)
    
    draft_pick = relationship("DraftPick", back_populates="player", uselist=False)

# --- 5. DRAFT PICK TABLE ---
class DraftPick(Base):
    __tablename__ = "draft_picks"
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer)
    round_num = Column(Integer, nullable=True)
    pick_num = Column(Integer, nullable=True)
    amount = Column(Integer) 
    session_id = Column(String, default="default") 
    current_status = Column(String, default='BENCH') 
    timestamp = Column(String, nullable=True) 

    owner_id = Column(Integer, ForeignKey("users.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True)
    
    owner = relationship("User", back_populates="picks")
    player = relationship("Player", back_populates="draft_pick")
    league = relationship("League", back_populates="draft_picks")

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
    points = Column(Float, default=0) 
    
    league = relationship("League", back_populates="scoring_rules")

# --- 8. WAIVER CLAIMS ---
class WaiverClaim(Base):
    __tablename__ = "waiver_claims"
    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    drop_player_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    
    bid_amount = Column(Integer, default=0)
    status = Column(String, default="PENDING") 
    
    user = relationship("User", back_populates="claims")
    league = relationship("League", back_populates="waiver_claims")
    target_player = relationship("Player", foreign_keys=[player_id])
    drop_player = relationship("Player", foreign_keys=[drop_player_id])