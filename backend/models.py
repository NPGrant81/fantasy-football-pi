from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from database import Base

# 1. USERS (Formerly 'OwnerID.csv')
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)  # For Epic 1.5 (Login)
    
    # Relationships
    team = relationship("FantasyTeam", back_populates="owner", uselist=False)

# 2. FANTASY TEAMS (New Table to link Users to Rosters)
class FantasyTeam(Base):
    __tablename__ = "fantasy_teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="My Team")
    user_id = Column(Integer, ForeignKey("users.id"))
    remaining_budget = Column(Integer, default=200) # Budget for auction
    
    owner = relationship("User", back_populates="team")
    roster = relationship("Roster", back_populates="fantasy_team")
    draft_picks = relationship("DraftResult", back_populates="fantasy_team")

# 3. PLAYERS (Formerly 'PlayerID.csv')
class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    position = Column(String)    # QB, RB, WR, etc.
    nfl_team = Column(String)    # KC, PHI, etc.
    active = Column(Boolean, default=True) # To filter out retired players
    
    # Relationships
    draft_info = relationship("DraftResult", back_populates="player")
    roster_spot = relationship("Roster", back_populates="player")

# 4. DRAFT RESULTS (Formerly 'DraftResult.csv')
class DraftResult(Base):
    __tablename__ = "draft_results"

    id = Column(Integer, primary_key=True, index=True)
    season_year = Column(Integer)
    amount = Column(Integer)  # Auction cost
    
    player_id = Column(Integer, ForeignKey("players.id"))
    team_id = Column(Integer, ForeignKey("fantasy_teams.id"))
    
    player = relationship("Player", back_populates="draft_info")
    fantasy_team = relationship("FantasyTeam", back_populates="draft_picks")

# 5. CURRENT ROSTER (New table for current week state)
class Roster(Base):
    __tablename__ = "rosters"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("fantasy_teams.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    is_starter = Column(Boolean, default=False)
    
    fantasy_team = relationship("FantasyTeam", back_populates="roster")
    player = relationship("Player", back_populates="roster_spot")
