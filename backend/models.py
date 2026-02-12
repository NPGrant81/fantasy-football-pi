from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, JSON, Enum as SqlEnum
from sqlalchemy.orm import relationship
from database import Base
import enum

# --- 0. ENUMS (Permissions) ---
class UserRole(str, enum.Enum):
    ADMIN = "admin"           # Site Owner (You)
    COMMISSIONER = "commish"  # League Manager
    USER = "user"             # Regular Owner

# --- 1. LEAGUE TABLE ---
class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    
    users = relationship("User", back_populates="league")
    # Link to the new detailed scoring rules
    scoring_rules = relationship("ScoringRule", back_populates="league")

# --- 2. LEAGUE SETTINGS (General Config) ---
class LeagueSettings(Base):
    __tablename__ = "league_settings"

    id = Column(Integer, primary_key=True, index=True)
    # Link this to a specific league (Best Practice)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True)

    league_name = Column(String, default="My Fantasy League")
    
    # Roster Rules
    roster_size = Column(Integer, default=14)
    salary_cap = Column(Integer, default=200)
    
    # Starting Slots (stored as JSON)
    starting_slots = Column(JSON, default={
        "QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1, "FLEX": 1
    })
    
    # Basic Scoring (JSON for simple stuff like "1 pt per 10 yards")
    simple_scoring_json = Column(JSON, default=[])

# --- 3. USER TABLE (The Team Owner) ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    # --- NEW: Permissions & Divisions ---
    role = Column(SqlEnum(UserRole), default=UserRole.USER)
    is_commissioner = Column(Boolean, default=False)
    division = Column(String, nullable=True)

    # Relationship to League
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True) 
    league = relationship("League", back_populates="users")
    
    picks = relationship("DraftPick", back_populates="owner")
    
    # FIX: Removed the brackets [] from the strings below
    home_matches = relationship("Matchup", foreign_keys="Matchup.home_team_id", back_populates="home_team")
    away_matches = relationship("Matchup", foreign_keys="Matchup.away_team_id", back_populates="away_team")
    
# --- 4. PLAYER TABLE ---
class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    position = Column(String)
    nfl_team = Column(String)
    gsis_id = Column(String, nullable=True, unique=True) # Vital for nfl_data_py syncing
    bye_week = Column(Integer, nullable=True)

# --- 5. DRAFT PICK TABLE (Your Roster) ---
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
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True) # Good to track which league this game belongs to

    home_team_id = Column(Integer, ForeignKey("users.id"))
    away_team_id = Column(Integer, ForeignKey("users.id"))
    
    # Actual Scores
    home_score = Column(Float, default=0.0)
    away_score = Column(Float, default=0.0)

    # Projected Scores
    home_projected = Column(Float, default=0.0)
    away_projected = Column(Float, default=0.0)
    
    is_completed = Column(Boolean, default=False)

    # Relationships
    home_team = relationship("User", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("User", foreign_keys=[away_team_id], back_populates="away_matches")

# --- 8. SCORING RULES (The New Engine) ---
class ScoringRule(Base):
    """
    Complex scoring rules.
    Example: category="passing_td_length", min=40, max=49, points=2.0
    """
    __tablename__ = "scoring_rules"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    
    category = Column(String) # e.g. "PASS_TD_LENGTH", "RUSH_YARDS"
    min_val = Column(Float, default=0) # e.g. 40
    max_val = Column(Float, default=999) # e.g. 49
    points = Column(Float, default=0) # e.g. 2.0
    # ADD THIS LINE so the AI knows what the rule is describing
    description = Column(String, nullable=True)
    # Logic Filters
    position_target = Column(String, nullable=True) # e.g. "QB" (If only QBs get this rule)
    
    league = relationship("League", back_populates="scoring_rules")
