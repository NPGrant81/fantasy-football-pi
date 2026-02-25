from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON, UniqueConstraint
# use generic JSON to allow sqlite tests; Postgres will use native JSON/JSONB automatically
# from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
# ensure Base always comes from backend.database regardless of context
import importlib
Base = importlib.import_module("backend.database").Base

# --- 1. PLAYER ID MAPPINGS ---
class PlayerIDMapping(Base):
    __tablename__ = "player_id_mappings"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    yahoo_id = Column(String, nullable=True)
    espn_id = Column(String, nullable=True)
    draftsharks_id = Column(String, nullable=True)
    fantasypros_id = Column(String, nullable=True)

# --- 2. PLATFORM PROJECTIONS (RAW FACT TABLE) ---
class PlatformProjection(Base):
    __tablename__ = "platform_projections"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    source = Column(String, nullable=False)  # e.g., 'Yahoo', 'ESPN', 'DraftSharks'
    season = Column(Integer, nullable=False)
    projected_points = Column(Float, nullable=True)
    adp = Column(Float, nullable=True)
    auction_value = Column(Float, nullable=True)
    position_rank = Column(Integer, nullable=True)
    raw_json = Column(JSON, nullable=True)  # Store raw payload for audit/debug
    created_at = Column(String, nullable=True)

# --- 3. DRAFT VALUES (AGGREGATED/CONSENSUS TABLE) ---
class DraftValue(Base):
    __tablename__ = "draft_values"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_draft_value_player_season"),
    )
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    season = Column(Integer, nullable=False)
    avg_auction_value = Column(Float, nullable=True)
    median_adp = Column(Float, nullable=True)
    consensus_tier = Column(String, nullable=True)
    value_over_replacement = Column(Float, nullable=True)
    last_updated = Column(String, nullable=True)

