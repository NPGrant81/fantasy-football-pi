"""
Load normalized Yahoo draft value data into PostgreSQL tables.
- Uses gsis_id as master key for player normalization.
- Inserts new Player records if no match is found.
- Updates player_id_mappings with Yahoo ID.
"""
import os
import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ensure the repository root is on sys.path so that the ``backend`` package
# can be imported regardless of the current working directory.  previously we
# used a try/except with bare imports; that pattern confused Pylance and
# resulted in unresolved-import errors in the Problems panel.
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.models import Player
from backend.models_draft_value import DraftValue, PlayerIDMapping, PlatformProjection
from backend.database import Base
from etl.validation.dataframe_validation import validate_normalized_players_dataframe
from etl.validation.great_expectations_runner import run_normalized_players_expectations

# Update this with your actual DB URL or use env var
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password123@localhost/fantasy_pi")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def load_normalized_source_to_db(norm_df: pd.DataFrame, season: int, source: str):
    dataframe_report = validate_normalized_players_dataframe(norm_df)
    if not dataframe_report.valid:
        raise ValueError(
            f"DataFrame validation failed ({dataframe_report.engine}): {dataframe_report.errors}"
        )

    expectation_report = run_normalized_players_expectations(norm_df)
    if not expectation_report.success:
        raise ValueError(
            f"Expectation validation failed ({expectation_report.engine}): {expectation_report.details}"
        )

    session = SessionLocal()
    for _, row in norm_df.iterrows():
        # Try to find Player by gsis_id, fallback to name/position/team
        player = None
        if row.get('gsis_id'):
            player = session.query(Player).filter_by(gsis_id=row['gsis_id']).first()
        if not player:
            # Use only the base position (e.g., 'WR', 'RB', etc.) for Player.position
            base_position = row.get('position')
            if not base_position and row.get('position_rank'):
                import re
                match = re.match(r"[A-Z]+", str(row.get('position_rank')))
                base_position = match.group(0) if match else None
            player = session.query(Player).filter_by(
                name=row['normalized_name'],
                position=base_position,
                nfl_team=row.get('team') or row.get('pro_team_id')
            ).first()
        if not player:
            base_position = row.get('position')
            if not base_position and row.get('position_rank'):
                import re
                match = re.match(r"[A-Z]+", str(row.get('position_rank')))
                base_position = match.group(0) if match else None
            player = Player(
                name=row['normalized_name'],
                position=base_position,
                nfl_team=row.get('team') or row.get('pro_team_id'),
                bye_week=row.get('bye_week'),
                gsis_id=row.get('gsis_id')
            )
            session.add(player)
            session.flush()  # Get new player.id
        # Update player_id_mappings for each source
        mapping = session.query(PlayerIDMapping).filter_by(player_id=player.id).first()
        if not mapping:
            mapping = PlayerIDMapping(player_id=player.id)
        if source.lower() == 'yahoo':
            mapping.yahoo_id = row.get('yahoo_id')
        elif source.lower() == 'espn':
            mapping.espn_id = row.get('espn_id')
        elif source.lower() == 'draftsharks':
            mapping.draftsharks_id = row.get('draftsharks_id')
        session.add(mapping)
        # Insert platform projection (raw fact)
        # Ensure position_rank is always an integer for DB
        from etl.transform.normalize import extract_position_rank
        projection = PlatformProjection(
            player_id=player.id,
            source=source,
            season=season,
            projected_points=row.get('projected_points'),
            adp=row.get('adp'),
            auction_value=row.get('auction_value'),
            position_rank=extract_position_rank(row.get('position_rank')),
            raw_json=row.to_dict()
        )
        session.add(projection)
    session.commit()
    session.close()


def load_historical_rankings_to_db(rankings_df: pd.DataFrame, season: int):
    required_columns = {
        "player_id",
        "predicted_auction_value",
        "median_bid",
        "value_over_replacement",
        "consensus_tier",
    }
    missing = required_columns - set(rankings_df.columns)
    if missing:
        raise ValueError(f"Rankings DataFrame missing required columns: {sorted(missing)}")

    session = SessionLocal()
    for _, row in rankings_df.iterrows():
        player_id = int(row["player_id"])
        existing = (
            session.query(DraftValue)
            .filter(
                DraftValue.player_id == player_id,
                DraftValue.season == season,
            )
            .first()
        )
        if not existing:
            existing = DraftValue(player_id=player_id, season=season)
            session.add(existing)

        existing.avg_auction_value = float(row.get("predicted_auction_value") or 0)
        existing.median_adp = float(row.get("median_bid") or 0)
        existing.consensus_tier = str(row.get("consensus_tier") or "C")
        existing.value_over_replacement = float(row.get("value_over_replacement") or 0)
        existing.last_updated = pd.Timestamp.utcnow().isoformat()

    session.commit()
    session.close()

# Example usage for each source:
if __name__ == "__main__":
    # Yahoo
    # norm_df = pd.read_csv('yahoo_top_players_normalized.csv')
    # load_normalized_source_to_db(norm_df, season=2025, source='Yahoo')
    # DraftSharks
    # norm_df = pd.read_csv('draftsharks_adp_normalized.csv')
    # load_normalized_source_to_db(norm_df, season=2025, source='DraftSharks')
    # ESPN
    # norm_df = pd.read_csv('espn_top_300_normalized.csv')
    # load_normalized_source_to_db(norm_df, season=2025, source='ESPN')
    print("Loaded normalized data to database.")
