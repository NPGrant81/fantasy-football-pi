from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database import Base

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
    bug_reports = relationship("BugReport", back_populates="user")

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
    waiver_deadline = Column(String, nullable=True)  # ISO format string, set by commissioner
    draft_year = Column(Integer, nullable=True)
    
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
    espn_id = Column(String, nullable=True, unique=True)
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

# --- 5.1 DRAFT BUDGETS ---
class DraftBudget(Base):
    __tablename__ = "draft_budgets"
    __table_args__ = (
        UniqueConstraint("league_id", "owner_id", "year", name="uq_budget_league_owner_year"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    owner_id = Column(Integer, ForeignKey("users.id"))
    year = Column(Integer, index=True)
    total_budget = Column(Integer, default=200)

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

# --- 9. BUG REPORTS ---
class BugReport(Base):
    __tablename__ = "bug_reports"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    email = Column(String, nullable=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    page_name = Column(String, nullable=True)
    issue_type = Column(String, nullable=True)
    page_url = Column(String, nullable=True)
    github_issue_url = Column(String, nullable=True)
    status = Column(String, default="OPEN")
    created_at = Column(String, nullable=True)

    user = relationship("User", back_populates="bug_reports")

# --- 10. PLAYER WEEKLY STATS ---
class PlayerWeeklyStat(Base):
    __tablename__ = "player_weekly_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "week", "source", name="uq_player_week_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    season = Column(Integer, index=True)
    week = Column(Integer, index=True)
    fantasy_points = Column(Float, nullable=True)
    stats = Column(JSON, nullable=True)
    source = Column(String, default="espn")
    created_at = Column(String, nullable=True)

    player = relationship("Player")


# --- 11. TRADE PROPOSALS ---
class TradeProposal(Base):
    __tablename__ = "trade_proposals"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    offered_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    requested_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    note = Column(String, nullable=True)
    status = Column(String, default="PENDING")
    created_at = Column(String, nullable=True)


# --- 13. UNMATCHED PLAYERS (Dead Letter Queue) ---
class UnmatchedPlayer(Base):
    __tablename__ = "unmatched_players"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)  # e.g., 'Yahoo', 'ESPN', etc.
    scraped_name = Column(String, index=True)
    team = Column(String, nullable=True)
    position = Column(String, nullable=True)
    extra_data = Column(JSON, nullable=True)  # Any additional info (raw row, etc.)
    created_at = Column(String, nullable=True)

# --- 14. MANUAL PLAYER MAPPINGS ---
class ManualPlayerMapping(Base):
    __tablename__ = "manual_player_mappings"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)
    scraped_name = Column(String, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    mapped_at = Column(String, nullable=True)
    # Optionally: team, position, notes
    team = Column(String, nullable=True)
    position = Column(String, nullable=True)
    notes = Column(String, nullable=True)