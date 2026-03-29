"""
Load normalized Yahoo draft value data into PostgreSQL tables.
- Uses gsis_id as master key for player normalization.
- Inserts new Player records if no match is found.
- Updates player_id_mappings with Yahoo ID.
"""
import os
import sys
import re
from difflib import SequenceMatcher
from pathlib import Path
import pandas as pd
from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.orm import sessionmaker

# ensure the repository root is on sys.path so that the ``backend`` package
# can be imported regardless of the current working directory.  previously we
# used a try/except with bare imports; that pattern confused Pylance and
# resulted in unresolved-import errors in the Problems panel.
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.models import Player
from backend.models_draft_value import DraftValue, PlayerIDMapping, PlatformProjection
from backend.db_config import load_backend_env_file, resolve_database_url
from etl.transform.normalize import extract_position_rank, normalize_player_name
from etl.validation.dataframe_validation import validate_normalized_players_dataframe
from etl.validation.great_expectations_runner import run_normalized_players_expectations

load_backend_env_file()
DATABASE_URL = resolve_database_url(require_explicit=True, context="etl/load/load_to_postgres.py")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

TEAM_ALIASES = {
    "JAC": "JAX",
    "WSH": "WAS",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
}


def _normalize_team_code(value):
    text = str(value or "").strip().upper()
    if not text:
        return None
    return TEAM_ALIASES.get(text, text)


def _base_position_from_row(row) -> str | None:
    base_position = row.get('position')
    if base_position:
        return str(base_position).strip().upper() or None
    if row.get('position_rank'):
        match = re.match(r"[A-Z]+", str(row.get('position_rank')).upper())
        return match.group(0) if match else None
    return None


def _source_key(source: str) -> str:
    key = str(source or "").strip().lower()
    if key.startswith("espn"):
        return "espn"
    if key.startswith("draftsharks"):
        return "draftsharks"
    if key.startswith("yahoo"):
        return "yahoo"
    return key


def _row_source_id(row, source_key: str):
    if source_key == "espn":
        return row.get('espn_id')
    if source_key == "draftsharks":
        return row.get('draftsharks_id')
    if source_key == "yahoo":
        return row.get('yahoo_id')
    return None


def _find_player_by_source_mapping(session, source_key: str, source_id):
    if source_id in (None, ""):
        return None

    source_id = str(source_id)
    query = session.query(PlayerIDMapping)
    if source_key == "espn":
        mapping = query.filter(PlayerIDMapping.espn_id == source_id).first()
    elif source_key == "draftsharks":
        mapping = query.filter(PlayerIDMapping.draftsharks_id == source_id).first()
    elif source_key == "yahoo":
        mapping = query.filter(PlayerIDMapping.yahoo_id == source_id).first()
    else:
        mapping = None

    if mapping and mapping.player_id:
        return session.get(Player, int(mapping.player_id))
    return None


def _find_player_by_exact_identity(session, normalized_name: str, base_position: str | None, team_code: str | None):
    if not normalized_name or not base_position:
        return None
    query = session.query(Player).filter(
        Player.name == normalized_name,
        Player.position == base_position,
    )
    if team_code:
        query = query.filter(Player.nfl_team == team_code)
    return query.order_by(Player.id.desc()).first()


def _find_player_by_fuzzy_identity(session, normalized_name: str, base_position: str | None, team_code: str | None):
    if not normalized_name or not base_position:
        return None
    if len(normalized_name) < 4:
        return None

    query = session.query(Player).filter(Player.position == base_position)
    if team_code:
        query = query.filter(Player.nfl_team == team_code)

    candidates = query.limit(500).all()
    best = None
    best_score = 0.0
    target = normalize_player_name(normalized_name)
    for candidate in candidates:
        candidate_name = normalize_player_name(candidate.name or "")
        score = SequenceMatcher(None, target, candidate_name).ratio()
        if score > best_score:
            best = candidate
            best_score = score

    threshold = 0.90 if team_code else 0.96
    if best is not None and best_score >= threshold:
        return best
    return None


def _upsert_platform_projection(session, *, player_id: int, source: str, season: int, row_dict: dict):
    existing_rows = (
        session.query(PlatformProjection)
        .filter_by(player_id=player_id, source=source, season=season)
        .order_by(PlatformProjection.id.asc())
        .all()
    )

    target = existing_rows[0] if existing_rows else PlatformProjection(
        player_id=player_id,
        source=source,
        season=season,
    )
    target.projected_points = row_dict.get('projected_points')
    target.adp = row_dict.get('adp')
    target.auction_value = row_dict.get('auction_value')
    target.position_rank = extract_position_rank(row_dict.get('position_rank'))
    target.raw_json = row_dict
    session.add(target)

    for duplicate in existing_rows[1:]:
        session.delete(duplicate)


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
    source_key = _source_key(source)
    for _, row in norm_df.iterrows():
        row_data = row.to_dict()
        normalized_name = str(row_data.get('normalized_name') or '').strip().lower()
        team_code = _normalize_team_code(row_data.get('team') or row_data.get('pro_team_id'))
        base_position = _base_position_from_row(row_data)

        # Try to find Player by gsis_id, fallback to name/position/team
        player = None
        if row_data.get('gsis_id'):
            player = session.query(Player).filter_by(gsis_id=row_data['gsis_id']).first()
        if not player:
            player = _find_player_by_source_mapping(
                session,
                source_key=source_key,
                source_id=_row_source_id(row_data, source_key),
            )
        if not player:
            player = _find_player_by_exact_identity(
                session,
                normalized_name=normalized_name,
                base_position=base_position,
                team_code=team_code,
            )
        if not player:
            player = _find_player_by_fuzzy_identity(
                session,
                normalized_name=normalized_name,
                base_position=base_position,
                team_code=team_code,
            )
        if not player:
            player = Player(
                name=normalized_name,
                position=base_position,
                nfl_team=team_code,
                bye_week=row_data.get('bye_week'),
                gsis_id=row_data.get('gsis_id')
            )
            session.add(player)
            session.flush()  # Get new player.id

        # Update player_id_mappings for each source
        mapping = session.query(PlayerIDMapping).filter_by(player_id=player.id).first()
        if not mapping:
            mapping = PlayerIDMapping(player_id=player.id)
        if source_key == 'yahoo':
            mapping.yahoo_id = row_data.get('yahoo_id')
        elif source_key == 'espn':
            mapping.espn_id = row_data.get('espn_id')
        elif source_key == 'draftsharks':
            mapping.draftsharks_id = row_data.get('draftsharks_id')
        session.add(mapping)

        _upsert_platform_projection(
            session,
            player_id=int(player.id),
            source=source,
            season=season,
            row_dict=row_data,
        )

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
    try:
        # Reflect the live table to tolerate environments where the DB schema
        # lags behind ORM-only columns (e.g., local sqlite test DBs).
        draft_values = Table("draft_values", MetaData(), autoload_with=engine)
        available_columns = set(draft_values.c.keys())

        for _, row in rankings_df.iterrows():
            player_id = int(row["player_id"])

            values: dict[str, object] = {}
            if "avg_auction_value" in available_columns:
                values["avg_auction_value"] = float(row.get("predicted_auction_value") or 0)
            if "median_adp" in available_columns:
                values["median_adp"] = float(row.get("median_bid") or 0)
            if "consensus_tier" in available_columns:
                values["consensus_tier"] = str(row.get("consensus_tier") or "C")
            if "value_over_replacement" in available_columns:
                values["value_over_replacement"] = float(row.get("value_over_replacement") or 0)
            if "last_updated" in available_columns:
                values["last_updated"] = pd.Timestamp.utcnow().isoformat()

            existing_id = session.execute(
                select(draft_values.c.id).where(
                    draft_values.c.player_id == player_id,
                    draft_values.c.season == season,
                )
            ).scalar_one_or_none()

            if existing_id is None:
                insert_values = {
                    "player_id": player_id,
                    "season": season,
                    **values,
                }
                session.execute(draft_values.insert().values(**insert_values))
            elif values:
                session.execute(
                    draft_values.update()
                    .where(draft_values.c.id == existing_id)
                    .values(**values)
                )

        session.commit()
    finally:
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
