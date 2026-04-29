from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, JSON, Numeric, DateTime, func, UniqueConstraint, Index, event
from sqlalchemy.orm import relationship
# import backend.database explicitly so the module is always named backend.database
import importlib
Base = importlib.import_module("backend.database").Base

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
    # new division mapping -- optional FK
    division_id = Column(Integer, ForeignKey("divisions.id"), nullable=True)
    team_name = Column(String, nullable=True)
    future_draft_budget = Column(Integer, default=0)  # dollars available for future drafts
    
    # 1.3 TEAM VISUAL ASSETS
    team_logo_url = Column(String, nullable=True)
    team_color_primary = Column(String, nullable=True, default='#3b82f6')  # blue-500
    team_color_secondary = Column(String, nullable=True, default='#1e40af')  # blue-800

    # relationships
    division_obj = relationship("Division", back_populates="users")
    # Relationships
    league = relationship("League", back_populates="users") 
    picks = relationship("DraftPick", back_populates="owner")
    claims = relationship("WaiverClaim", back_populates="user")
    home_matches = relationship("Matchup", foreign_keys="Matchup.home_team_id", back_populates="home_team")
    away_matches = relationship("Matchup", foreign_keys="Matchup.away_team_id", back_populates="away_team")
    bug_reports = relationship("BugReport", back_populates="user")
    scoring_rule_changes = relationship("ScoringRuleChangeLog", foreign_keys="ScoringRuleChangeLog.changed_by_user_id", back_populates="changed_by_user")
    scoring_rule_proposals = relationship("ScoringRuleProposal", foreign_keys="ScoringRuleProposal.proposed_by_user_id", back_populates="proposed_by_user")
    scoring_rule_votes = relationship("ScoringRuleVote", foreign_keys="ScoringRuleVote.voter_user_id", back_populates="voter_user")

# --- 2. LEAGUE TABLE ---
class League(Base):
    __tablename__ = "leagues"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    draft_status = Column(String, default="PRE_DRAFT") 
    created_at = Column(String, nullable=True)
    # tracks the calendar year of the currently active/live season
    current_season = Column(Integer, nullable=True, index=True)

    # Relationships
    users = relationship("User", back_populates="league")
    scoring_rules = relationship("ScoringRule", back_populates="league")
    settings = relationship("LeagueSettings", back_populates="league", uselist=False)
    divisions = relationship("Division", back_populates="league")
    matchups = relationship("Matchup", back_populates="league")
    draft_picks = relationship("DraftPick", back_populates="league")
    waiver_claims = relationship("WaiverClaim", back_populates="league")
    playoff_snapshots = relationship("PlayoffSnapshot", back_populates="league")
    scoring_templates = relationship("ScoringTemplate", back_populates="league")
    scoring_rule_changes = relationship("ScoringRuleChangeLog", back_populates="league")
    scoring_rule_proposals = relationship("ScoringRuleProposal", back_populates="league")
    mfl_seasons = relationship("LeagueMflSeason", back_populates="league", order_by="LeagueMflSeason.season")

# --- 2.1 LEAGUE MFL SEASON MAPPING ---
class LeagueMflSeason(Base):
    """Maps each app league to its MFL source league ID for a given season year.

    MFL assigns a new numeric league ID every season, so this table is the
    canonical resolver: (app_league_id, season) → mfl_source_league_id.
    Used by the historical import pipeline and for future season rollover.
    """
    __tablename__ = "league_mfl_seasons"
    __table_args__ = (
        UniqueConstraint("league_id", "season", name="uq_league_mfl_season"),
    )
    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    season = Column(Integer, nullable=False, index=True)
    # The numeric ID MFL assigned to this league for this season year
    mfl_league_id = Column(String, nullable=False)
    mfl_franchise_count = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    league = relationship("League", back_populates="mfl_seasons")


class LeagueHistoryTeamOwnerMap(Base):
    """Manual mapping of historical team labels to owner names by league and season."""

    __tablename__ = "league_history_team_owner_map"
    __table_args__ = (
        UniqueConstraint(
            "league_id",
            "season",
            "team_name_key",
            name="uq_league_history_team_owner_map_key",
        ),
        Index("ix_league_history_team_owner_map_league", "league_id"),
        Index("ix_league_history_team_owner_map_season", "season"),
        Index("ix_league_history_team_owner_map_team_key", "team_name_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    season = Column(Integer, nullable=False)
    team_name = Column(String(160), nullable=False)
    team_name_key = Column(String(160), nullable=False)
    owner_name = Column(String(160), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    league = relationship("League")
    owner = relationship("User")


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
    starting_waiver_budget = Column(Integer, default=100)
    waiver_system = Column(String, default='FAAB')
    waiver_tiebreaker = Column(String, default='standings')
    trade_deadline = Column(String, nullable=True)   # new trade deadline option
    trade_start_at = Column(DateTime(timezone=True), nullable=True)
    trade_end_at = Column(DateTime(timezone=True), nullable=True)
    allow_playoff_trades = Column(Boolean, nullable=False, default=True)
    require_commissioner_approval = Column(Boolean, nullable=False, default=True)

    # --- Trade governance rules ---
    trade_veto_enabled = Column(Boolean, nullable=False, default=False)
    trade_veto_threshold = Column(Integer, nullable=True)            # number of owner votes required to veto
    trade_review_period_hours = Column(Integer, nullable=True)       # hours commissioner/league has to review/veto
    trade_max_players_per_side = Column(Integer, nullable=True)      # max players each side may include
    trade_league_vote_enabled = Column(Boolean, nullable=False, default=False)
    trade_league_vote_threshold = Column(Integer, nullable=True)     # % of owners required to approve
    draft_year = Column(Integer, nullable=True)
    future_draft_cap = Column(Integer, default=0)  # maximum dollars each owner may start with

    # --- Playoff configuration ---
    playoff_qualifiers = Column(Integer, default=6)
    playoff_reseed = Column(Boolean, default=False)
    playoff_consolation = Column(Boolean, default=True)
    playoff_tiebreakers = Column(
        JSON,
        default=["overall_record", "head_to_head", "points_for", "points_against", "random_draw"],
    )

    # --- Divisions configuration ---
    divisions_enabled = Column(Boolean, default=False)
    division_count = Column(Integer, nullable=True)
    division_config_status = Column(String, default="draft")  # draft|finalized
    division_assignment_method = Column(String, nullable=True)  # manual|random|heuristic
    division_random_seed = Column(String, nullable=True)
    division_needs_reseed = Column(Boolean, default=False)
    division_history_enabled = Column(Boolean, default=True)

    league = relationship("League", back_populates="settings")


# --- 3.5 KEEPER RULES ---
class KeeperRules(Base):
    __tablename__ = "keeper_rules"
    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), unique=True)
    max_keepers = Column(Integer, default=3)
    max_years_per_player = Column(Integer, default=1)
    cost_type = Column(String, default="round")
    cost_inflation = Column(Integer, default=0)
    deadline_date = Column(DateTime(timezone=True), nullable=True)  # keeper lock datetime (UTC)
    waiver_policy = Column(Boolean, default=True)
    trade_deadline = Column(DateTime(timezone=True), nullable=True)
    drafted_only = Column(Boolean, default=True)

    league = relationship("League")

# --- 3.6 KEEPER ENTRIES ---
class Keeper(Base):
    __tablename__ = "keepers"
    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    season = Column(Integer, nullable=False)
    keep_cost = Column(Numeric, nullable=False)
    years_kept_count = Column(Integer, default=1)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_commish = Column(Boolean, default=False)
    status = Column(String, default="pending")
    flag_waiver = Column(Boolean, default=False)
    flag_trade = Column(Boolean, default=False)
    flag_drop = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    league = relationship("League")
    owner = relationship("User")
    player = relationship("Player")

# --- 3.1 LINEUP SUBMISSIONS ---
class LineupSubmission(Base):
    __tablename__ = "lineup_submissions"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    season = Column(Integer, index=True, nullable=False)
    week = Column(Integer, index=True, nullable=False)
    submitted_at = Column(String, nullable=True)

    # relationships could be added if needed

# --- 4. PLAYER TABLE ---

# --- 3.2 DIVISIONS ---
class Division(Base):
    __tablename__ = "divisions"
    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    season = Column(Integer, index=True, nullable=True)
    name = Column(String, nullable=False)
    order_index = Column(Integer, default=0)

    league = relationship("League", back_populates="divisions")
    users = relationship("User", back_populates="division_obj")


class DivisionConfigSnapshot(Base):
    __tablename__ = "division_config_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    season = Column(Integer, nullable=False, index=True)
    status = Column(String, default="draft", nullable=False)  # draft|finalized|undo
    assignment_method = Column(String, nullable=True)
    random_seed = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    imbalance_pct = Column(Float, nullable=True)
    config_json = Column(JSON, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    league = relationship("League")
    created_by = relationship("User", foreign_keys=[created_by_user_id])


class DivisionNameReport(Base):
    __tablename__ = "division_name_reports"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    season = Column(Integer, nullable=True, index=True)
    division_name = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    status = Column(String, default="open", nullable=False)  # open|resolved|dismissed
    reported_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    league = relationship("League")
    reported_by = relationship("User", foreign_keys=[reported_by_user_id])

# modify User to reference Division
# insert after user class definition modifications
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
    seasons = relationship("PlayerSeason", back_populates="player")
    aliases = relationship("PlayerAlias", back_populates="player")


class PlayerSeason(Base):
    __tablename__ = "player_seasons"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_season"),
    )

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    season = Column(Integer, nullable=False, index=True)
    nfl_team = Column(String, nullable=True)
    position = Column(String, nullable=True)
    bye_week = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    source = Column(String(32), nullable=False, default="sync")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    player = relationship("Player", back_populates="seasons")


class PlayerAlias(Base):
    __tablename__ = "player_aliases"
    __table_args__ = (
        UniqueConstraint("player_id", "alias_name", "source", name="uq_player_alias_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    alias_name = Column(String, nullable=False, index=True)
    source = Column(String(32), nullable=False, default="canonical")
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    player = relationship("Player", back_populates="aliases")


class PlayerNewsItem(Base):
    __tablename__ = "player_news_items"
    __table_args__ = (
        UniqueConstraint("league_id", "source", "source_item_id", name="uq_player_news_league_source_item"),
        Index("ix_player_news_league_published", "league_id", "published_at"),
        Index("ix_player_news_published", "published_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True, index=True)
    source = Column(String(64), nullable=False, default="internal")
    source_item_id = Column(String(128), nullable=False)
    title = Column(String, nullable=False)
    summary = Column(String, nullable=True)
    content = Column(String, nullable=True)
    url = Column(String, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sentiment_score = Column(Float, default=0.0)
    sentiment_label = Column(String(32), default="neutral")
    sentiment_tags = Column(JSON, default=list)
    meta_json = Column(JSON, nullable=True)

    league = relationship("League")
    links = relationship("PlayerNewsLink", back_populates="news_item", cascade="all,delete-orphan")


class PlayerNewsLink(Base):
    __tablename__ = "player_news_links"
    __table_args__ = (
        UniqueConstraint("news_item_id", "player_id", name="uq_player_news_player_link"),
        Index("ix_player_news_link_player", "player_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    news_item_id = Column(Integer, ForeignKey("player_news_items.id"), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    confidence = Column(Float, default=1.0)
    match_reason = Column(String(64), nullable=True)

    news_item = relationship("PlayerNewsItem", back_populates="links")
    player = relationship("Player")


class PlayerNewsSentimentTrend(Base):
    __tablename__ = "player_news_sentiment_trends"
    __table_args__ = (
        UniqueConstraint("league_id", "player_id", "window_hours", name="uq_news_trend_window"),
        Index("ix_news_trend_league_player", "league_id", "player_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    window_hours = Column(Integer, nullable=False)
    average_score = Column(Float, default=0.0)
    mention_count = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    league = relationship("League")
    player = relationship("Player")

# --- 5. DRAFT PICK TABLE ---

# --- 4.1 PLAYOFF SNAPSHOTS ---
class PlayoffSnapshot(Base):
    __tablename__ = "playoff_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    season = Column(Integer, index=True)
    data = Column(JSON, nullable=False)  # full bracket structure
    created_at = Column(String, nullable=True)

    league = relationship("League", back_populates="playoff_snapshots")


# --- 4.2 PLAYOFF MATCHES (CURRENT STATE) ---
class PlayoffMatch(Base):
    __tablename__ = "playoff_matches"
    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    season = Column(Integer, index=True)
    match_id = Column(String, index=True)
    round = Column(Integer, nullable=False)
    team_1_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    team_2_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    team_1_score = Column(Float, nullable=True)
    team_2_score = Column(Float, nullable=True)
    is_bye = Column(Boolean, default=False)
    winner_to = Column(String, nullable=True)
    team_1_seed = Column(Integer, nullable=True)
    team_2_seed = Column(Integer, nullable=True)
    team_1_is_division_winner = Column(Boolean, default=False)
    team_2_is_division_winner = Column(Boolean, default=False)

    league = relationship("League")

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

    # taxi flag indicates the player is on the taxi/elevated bench and not
    # eligible for starting lineup validation.  default is false for existing
    # data.
    is_taxi = Column(Boolean, default=False)

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


# --- 5.2 WAIVER BUDGETS (for FAAB tracking) ---
class WaiverBudget(Base):
    __tablename__ = "waiver_budgets"
    __table_args__ = (
        UniqueConstraint("league_id", "owner_id", name="uq_waiver_league_owner"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    owner_id = Column(Integer, ForeignKey("users.id"))
    starting_budget = Column(Integer, default=0)
    remaining_budget = Column(Integer, default=0)
    spent_budget = Column(Integer, default=0)

    # relationships can be added if needed
    year = Column(Integer, index=True)
    total_budget = Column(Integer, default=200)


# --- 5.3 NFL SCHEDULE ---
class NFLGame(Base):
    __tablename__ = "nfl_games"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True)
    season = Column(Integer, index=True)
    week = Column(Integer, index=True)
    home_team_id = Column(Integer)
    away_team_id = Column(Integer)
    kickoff = Column(String, nullable=True)  # ISO timestamp
    status = Column(String, default="PRE")
    home_score = Column(Integer, default=0)
    away_score = Column(Integer, default=0)
    # additional fields (odds, venue, etc.) can be added later

# --- 6. MATCHUP TABLE ---
class Matchup(Base):
    __tablename__ = "matchups"
    __table_args__ = (
        # Partial unique index enforced at DB level — season must be set for dedup to fire.
        # Prevents duplicate imports of historical data and live-season double-writes.
        Index(
            "uix_matchups_league_season_week_home_away",
            "league_id", "season", "week", "home_team_id", "away_team_id",
            unique=True,
            postgresql_where="season IS NOT NULL",
        ),
    )
    id = Column(Integer, primary_key=True, index=True)
    # Calendar year of the season this matchup belongs to (e.g. 2007, 2024).
    # Nullable for backward compat; all new rows (historical import + live) must set this.
    season = Column(Integer, index=True, nullable=True)
    week = Column(Integer, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True)

    home_team_id = Column(Integer, ForeignKey("users.id"))
    away_team_id = Column(Integer, ForeignKey("users.id"))
    home_score = Column(Float, default=0.0)
    away_score = Column(Float, default=0.0)
    is_completed = Column(Boolean, default=False)

    # Game status: NOT_STARTED, IN_PROGRESS, FINAL
    game_status = Column(String, default='NOT_STARTED')
    # True for playoff rounds; False for regular-season weeks
    is_playoff = Column(Boolean, default=False, nullable=False)
    is_division_matchup = Column(Boolean, default=False)
    is_rivalry_week = Column(Boolean, default=False)
    rivalry_name = Column(String, nullable=True)

    league = relationship("League", back_populates="matchups")
    home_team = relationship("User", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("User", foreign_keys=[away_team_id], back_populates="away_matches")

# --- 7. SCORING RULES ---
class ScoringRule(Base):
    __tablename__ = "scoring_rules"
    __table_args__ = (
        Index("ix_scoring_rules_lookup", "league_id", "season_year", "is_active", "event_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    season_year = Column(Integer, nullable=True, index=True)
    category = Column(String, nullable=False)            # high‑level grouping
    event_name = Column(String(100), nullable=False)     # textual rule name
    description = Column(String, nullable=True)

    range_min = Column(Numeric(10, 2), nullable=False, default=0)
    range_max = Column(Numeric(10, 2), nullable=False, default=9999.99)

    point_value = Column(Numeric(10, 2), nullable=False)
    calculation_type = Column(String, nullable=False, default="flat_bonus")

    # list of human-readable position codes (QB/RB/WR/TE/ALL)
    applicable_positions = Column(JSON, nullable=False, default=list)
    # list of numeric provider IDs (e.g. 8002/8003) for import parity
    position_ids = Column(JSON, nullable=False, default=list)

    source = Column(String(32), nullable=False, default="custom")  # custom|template|imported
    is_active = Column(Boolean, nullable=False, default=True)
    template_id = Column(Integer, ForeignKey("scoring_templates.id"), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    league = relationship("League", back_populates="scoring_rules")
    template = relationship("ScoringTemplate", back_populates="rules")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    updated_by_user = relationship("User", foreign_keys=[updated_by_user_id])
    template_links = relationship("ScoringTemplateRule", back_populates="scoring_rule")
    change_logs = relationship("ScoringRuleChangeLog", back_populates="scoring_rule")


class ScoringTemplate(Base):
    __tablename__ = "scoring_templates"
    __table_args__ = (
        UniqueConstraint("league_id", "name", "season_year", name="uq_scoring_template_league_name_season"),
        Index("ix_scoring_templates_lookup", "league_id", "season_year", "is_active"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    season_year = Column(Integer, nullable=True, index=True)
    name = Column(String(80), nullable=False)
    description = Column(String, nullable=True)
    source_platform = Column(String(32), nullable=False, default="custom")  # custom|espn|yahoo|nfl
    is_system_template = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    league = relationship("League", back_populates="scoring_templates")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    rules = relationship("ScoringRule", back_populates="template")
    template_rules = relationship("ScoringTemplateRule", back_populates="template")


class ScoringTemplateRule(Base):
    __tablename__ = "scoring_template_rules"
    __table_args__ = (
        UniqueConstraint("template_id", "scoring_rule_id", name="uq_scoring_template_rule_link"),
        Index("ix_scoring_template_rules_template_order", "template_id", "rule_order"),
    )

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("scoring_templates.id"), nullable=False)
    scoring_rule_id = Column(Integer, ForeignKey("scoring_rules.id"), nullable=False)
    rule_order = Column(Integer, nullable=False, default=0)
    included = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    template = relationship("ScoringTemplate", back_populates="template_rules")
    scoring_rule = relationship("ScoringRule", back_populates="template_links")


class ScoringRuleChangeLog(Base):
    __tablename__ = "scoring_rule_change_logs"
    __table_args__ = (
        Index("ix_scoring_rule_change_logs_lookup", "league_id", "season_year", "changed_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    scoring_rule_id = Column(Integer, ForeignKey("scoring_rules.id"), nullable=True)
    season_year = Column(Integer, nullable=True, index=True)
    change_type = Column(String(32), nullable=False)  # created|updated|deleted|imported|template_applied
    rationale = Column(String, nullable=True)
    previous_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    league = relationship("League", back_populates="scoring_rule_changes")
    scoring_rule = relationship("ScoringRule", back_populates="change_logs")
    changed_by_user = relationship("User", foreign_keys=[changed_by_user_id], back_populates="scoring_rule_changes")


class ScoringRuleProposal(Base):
    __tablename__ = "scoring_rule_proposals"
    __table_args__ = (
        Index("ix_scoring_rule_proposals_lookup", "league_id", "season_year", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    season_year = Column(Integer, nullable=True, index=True)
    title = Column(String(160), nullable=False)
    description = Column(String, nullable=True)
    proposed_change = Column(JSON, nullable=False)
    status = Column(String(24), nullable=False, default="open")  # open|approved|rejected|cancelled
    proposed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    voting_deadline = Column(DateTime(timezone=True), nullable=True)
    finalized_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    league = relationship("League", back_populates="scoring_rule_proposals")
    proposed_by_user = relationship("User", foreign_keys=[proposed_by_user_id], back_populates="scoring_rule_proposals")
    finalized_by_user = relationship("User", foreign_keys=[finalized_by_user_id])
    votes = relationship("ScoringRuleVote", back_populates="proposal")


class ScoringRuleVote(Base):
    __tablename__ = "scoring_rule_votes"
    __table_args__ = (
        UniqueConstraint("proposal_id", "voter_user_id", name="uq_scoring_rule_votes_proposal_voter"),
    )

    id = Column(Integer, primary_key=True, index=True)
    proposal_id = Column(Integer, ForeignKey("scoring_rule_proposals.id"), nullable=False)
    voter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vote = Column(String(16), nullable=False)  # yes|no|abstain
    vote_weight = Column(Numeric(6, 2), nullable=False, default=1)
    comment = Column(String, nullable=True)
    voted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    proposal = relationship("ScoringRuleProposal", back_populates="votes")
    voter_user = relationship("User", foreign_keys=[voter_user_id], back_populates="scoring_rule_votes")

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


class EconomicLedger(Base):
    __tablename__ = "economic_ledger"
    __table_args__ = (
        Index("ix_economic_ledger_owner_lookup", "league_id", "currency_type", "season_year", "to_owner_id", "from_owner_id"),
        Index("ix_economic_ledger_reference", "reference_type", "reference_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    season_year = Column(Integer, nullable=True, index=True)
    currency_type = Column(String, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    from_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    to_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    transaction_type = Column(String, nullable=False, index=True)
    reference_type = Column(String, nullable=True, index=True)
    reference_id = Column(String, nullable=True, index=True)
    notes = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    league = relationship("League")
    from_owner = relationship("User", foreign_keys=[from_owner_id])
    to_owner = relationship("User", foreign_keys=[to_owner_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])


@event.listens_for(EconomicLedger, "before_update")
def _prevent_ledger_update(mapper, connection, target):
    raise ValueError("economic_ledger is append-only and does not allow updates")


@event.listens_for(EconomicLedger, "before_delete")
def _prevent_ledger_delete(mapper, connection, target):
    raise ValueError("economic_ledger is append-only and does not allow deletes")


# --- 9. TRANSACTION HISTORY ---
class TransactionHistory(Base):
    __tablename__ = "transaction_history"
    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    # Calendar year of the season this transaction belongs to (e.g. 2007, 2024).
    # Nullable for backward compat; all new rows must set this.
    season = Column(Integer, index=True, nullable=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    old_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    new_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    transaction_type = Column(String, nullable=False)  # draft, trade, waiver_add, waiver_drop, drop
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(String, nullable=True)

    league = relationship("League")
    player = relationship("Player")
    old_owner = relationship("User", foreign_keys=[old_owner_id])
    new_owner = relationship("User", foreign_keys=[new_owner_id])

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


# --- 10. SITE VISITS ---
class SiteVisit(Base):
    __tablename__ = "site_visits"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    path = Column(String, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String, nullable=False, index=True)
    user_agent = Column(String, nullable=True)
    referrer = Column(String, nullable=True)
    client_timestamp = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")

# --- 11. PLAYER WEEKLY STATS ---
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


# --- 12. MANAGER EFFICIENCY (Analytics) ---
class ManagerEfficiency(Base):
    __tablename__ = "manager_efficiency"
    __table_args__ = (
        UniqueConstraint("league_id", "manager_id", "season", "week", name="uq_mgr_eff_league_mgr_season_week"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, index=True, nullable=False)
    manager_id = Column(Integer, index=True, nullable=False)
    season = Column(Integer, index=True, nullable=False)
    week = Column(Integer, index=True, nullable=False)

    actual_points_total = Column(Numeric(10, 2), default=0.00)
    optimal_points_total = Column(Numeric(10, 2), default=0.00)
    points_left_on_bench = Column(Numeric(10, 2))  # computed manually in ETL
    efficiency_rating = Column(Numeric(5, 4))
    optimal_lineup_json = Column(JSON, nullable=True)

    worst_sit_player_name = Column(String, nullable=True)
    worst_sit_points_diff = Column(Numeric(10, 2), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# --- 13. TRADE PROPOSALS ---
class TradeProposal(Base):
    __tablename__ = "trade_proposals"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    offered_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    requested_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    note = Column(String, nullable=True)
    offered_dollars = Column(Numeric, default=0)
    requested_dollars = Column(Numeric, default=0)
    status = Column(String, default="PENDING")
    created_at = Column(String, nullable=True)


# --- 13.5 TRADES (NEW WORKFLOW FOUNDATION) ---
class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_league_status", "league_id", "status"),
        Index("ix_trades_submitted_at", "submitted_at"),
        Index("ix_trades_teams", "team_a_id", "team_b_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    team_a_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    team_b_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(16), nullable=False, default="PENDING", index=True)
    commissioner_comments = Column(String, nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)

    league = relationship("League")
    team_a = relationship("User", foreign_keys=[team_a_id])
    team_b = relationship("User", foreign_keys=[team_b_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    assets = relationship("TradeAsset", back_populates="trade", cascade="all, delete-orphan")
    events = relationship("TradeEvent", back_populates="trade", cascade="all, delete-orphan")


class TradeAsset(Base):
    __tablename__ = "trade_assets"
    __table_args__ = (
        Index("ix_trade_assets_trade_side", "trade_id", "asset_side"),
        Index("ix_trade_assets_type", "asset_type"),
        Index("ix_trade_assets_player", "player_id"),
        Index("ix_trade_assets_draft_pick", "draft_pick_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False, index=True)
    asset_side = Column(String(1), nullable=False)  # A or B
    asset_type = Column(String(32), nullable=False)  # PLAYER, DRAFT_PICK, DRAFT_DOLLARS
    player_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    draft_pick_id = Column(Integer, ForeignKey("draft_picks.id"), nullable=True)
    amount = Column(Numeric, nullable=True)
    season_year = Column(Integer, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    trade = relationship("Trade", back_populates="assets")
    player = relationship("Player")
    draft_pick = relationship("DraftPick")


class TradeEvent(Base):
    __tablename__ = "trade_events"
    __table_args__ = (
        Index("ix_trade_events_trade_created", "trade_id", "created_at"),
        Index("ix_trade_events_type", "event_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False, index=True)
    event_type = Column(String(32), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    comment = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    trade = relationship("Trade", back_populates="events")
    actor_user = relationship("User", foreign_keys=[actor_user_id])


# --- 14. UNMATCHED PLAYERS (Dead Letter Queue) ---
class UnmatchedPlayer(Base):
    __tablename__ = "unmatched_players"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)  # e.g., 'Yahoo', 'ESPN', etc.
    scraped_name = Column(String, index=True)
    team = Column(String, nullable=True)
    position = Column(String, nullable=True)
    extra_data = Column(JSON, nullable=True)  # Any additional info (raw row, etc.)
    created_at = Column(String, nullable=True)

# --- 15. MANUAL PLAYER MAPPINGS ---
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


# --- 16. NORMALIZED MFL HTML RECORD FACTS ---
class MflHtmlRecordFact(Base):
    __tablename__ = "mfl_html_record_facts"
    __table_args__ = (
        UniqueConstraint("dataset_key", "row_fingerprint", name="uq_mfl_html_record_fact_dataset_fingerprint"),
        Index("ix_mfl_html_record_fact_dataset", "dataset_key"),
        Index("ix_mfl_html_record_fact_season", "season"),
        Index("ix_mfl_html_record_fact_target_league", "target_league_id"),
        Index("ix_mfl_html_record_fact_league", "league_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    dataset_key = Column(String(80), nullable=False)
    season = Column(Integer, nullable=True)
    target_league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True)
    league_id = Column(String(32), nullable=True)
    source_endpoint = Column(String(80), nullable=True)
    source_url = Column(String, nullable=True)
    extracted_at_utc = Column(String, nullable=True)
    normalization_version = Column(String(16), nullable=False, default="v1")
    row_fingerprint = Column(String(64), nullable=False)
    record_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MflIngestionRun(Base):
    __tablename__ = "mfl_ingestion_runs"
    __table_args__ = (
        Index("ix_mfl_ingestion_run_stage", "pipeline_stage"),
        Index("ix_mfl_ingestion_run_target_league", "target_league_id"),
        Index("ix_mfl_ingestion_run_status", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    pipeline_stage = Column(String(32), nullable=False)
    source_system = Column(String(32), nullable=False, default="mfl")
    target_league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True)
    status = Column(String(16), nullable=False, default="running")
    dry_run = Column(Boolean, nullable=False, default=False)
    truncate_before_load = Column(Boolean, nullable=False, default=False)
    input_roots = Column(JSON, nullable=False, default=list)
    command = Column(String, nullable=True)
    git_sha = Column(String(64), nullable=True)
    summary_json = Column(JSON, nullable=True)
    notes = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class MflIngestionFile(Base):
    __tablename__ = "mfl_ingestion_files"
    __table_args__ = (
        UniqueConstraint("run_id", "relative_path", name="uq_mfl_ingestion_file_run_path"),
        Index("ix_mfl_ingestion_file_run", "run_id"),
        Index("ix_mfl_ingestion_file_dataset", "dataset_key"),
        Index("ix_mfl_ingestion_file_source_league", "source_league_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("mfl_ingestion_runs.id"), nullable=False)
    dataset_key = Column(String(80), nullable=False)
    season = Column(Integer, nullable=True)
    source_league_id = Column(String(32), nullable=True)
    relative_path = Column(String, nullable=False)
    content_type = Column(String(32), nullable=False, default="text/csv")
    row_count = Column(Integer, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    sha256 = Column(String(64), nullable=True)
    retention_class = Column(String(32), nullable=True)
    archived_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)