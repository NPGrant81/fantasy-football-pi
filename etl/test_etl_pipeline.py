"""
Test script for ETL pipeline: extraction, transformation, and loading for Yahoo, DraftSharks, and ESPN.
"""

# --- Fix sys.path for module imports ---
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import pandas as pd
import logging
import json
import traceback
from datetime import datetime
from etl.extract.extract_yahoo import fetch_yahoo_top_players, transform_yahoo_players
from etl.extract.extract_draftsharks import scrape_draft_sharks_adp, transform_draftsharks_adp
from etl.extract.extract_espn_pdf import scrape_espn_2025_pdf
from etl.load.load_to_postgres import load_normalized_source_to_db
from etl.test_etl_utils import assert_not_empty, assert_columns_present, print_success, print_failure
from etl.slack_notifier import SlackNotifier

# --- Structured JSON Logging Setup ---
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'module': record.module,
            'message': record.getMessage(),
        }
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_record)

logger = logging.getLogger("etl")
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# --- Slack Notifier Setup ---
import os
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
notifier = SlackNotifier(SLACK_WEBHOOK_URL)

def test_yahoo_etl(season=2025):
    logger.info(json.dumps({"event": "start", "step": "yahoo_etl"}))
    players = fetch_yahoo_top_players()
    norm_df = pd.DataFrame(transform_yahoo_players(players))
    # --- Manual Mapping Integration ---
    from etl.transform.fetch_manual_mappings import fetch_manual_mappings_from_db
    from etl.transform.manual_mapping import apply_manual_mappings
    manual_mappings_df = fetch_manual_mappings_from_db()
    if not manual_mappings_df.empty:
        norm_df = apply_manual_mappings(norm_df, manual_mappings_df)
    try:
        assert_not_empty(norm_df, "Yahoo Normalized Data")
        assert_columns_present(norm_df, ["normalized_name", "position", "team", "adp"], "Yahoo Normalized Data")
        logger.info(json.dumps({"event": "success", "step": "yahoo_normalization"}))
    except AssertionError as e:
        logger.error(json.dumps({"event": "failure", "step": "yahoo_normalization", "error": str(e)}))
        return
    logger.info(json.dumps({"event": "data_sample", "step": "yahoo_etl", "sample": norm_df.head().to_dict()}))
    load_normalized_source_to_db(norm_df, season=season, source='Yahoo')
    logger.info(json.dumps({"event": "complete", "step": "yahoo_etl"}))

def test_draftsharks_etl(season=2025):
    logger.info(json.dumps({"event": "start", "step": "draftsharks_etl"}))
    ds_url = "https://www.draftsharks.com/adp/superflex/ppr/sleeper/12"
    df = scrape_draft_sharks_adp(ds_url)
    if df is not None:
        norm_df = transform_draftsharks_adp(df)
        # --- Manual Mapping Integration ---
        from etl.transform.fetch_manual_mappings import fetch_manual_mappings_from_db
        from etl.transform.manual_mapping import apply_manual_mappings
        manual_mappings_df = fetch_manual_mappings_from_db()
        if not manual_mappings_df.empty:
            norm_df = apply_manual_mappings(norm_df, manual_mappings_df)
        try:
            assert_not_empty(norm_df, "DraftSharks Normalized Data")
            assert_columns_present(norm_df, ["normalized_name", "position", "team", "adp"], "DraftSharks Normalized Data")
            logger.info(json.dumps({"event": "success", "step": "draftsharks_normalization"}))
        except AssertionError as e:
            logger.error(json.dumps({"event": "failure", "step": "draftsharks_normalization", "error": str(e)}))
            return
        logger.info(json.dumps({"event": "data_sample", "step": "draftsharks_etl", "sample": norm_df.head().to_dict()}))
        load_normalized_source_to_db(norm_df, season=season, source='DraftSharks')
        logger.info(json.dumps({"event": "complete", "step": "draftsharks_etl"}))

    logger.info(json.dumps({"event": "start", "step": "espn_etl_pdf_2025"}))
    pdf_url = "https://g.espncdn.com/s/ffldraftkit/25/NFL25_CS_PPR300.pdf?adddata=2025CS_PPR300"
    espn_df = scrape_espn_2025_pdf(pdf_url)
    if not espn_df.empty:
        espn_df["draft_year"] = 2025
        # Add normalized_name (copy of scraped_player_name for now)
        espn_df["normalized_name"] = espn_df["scraped_player_name"]
        # Add adp column (use auction_value or NaN if not available)
        espn_df["adp"] = espn_df["auction_value"] if "auction_value" in espn_df.columns else None
        # Ensure position and bye_week columns are present for DB loader
        if "position" not in espn_df.columns and "position_rank" in espn_df.columns:
            espn_df["position"] = espn_df["position_rank"].str.extract(r"([A-Z]+)")
        if "bye_week" not in espn_df.columns:
            espn_df["bye_week"] = None
        # Ensure position_rank is always integer for DB
        from etl.transform.normalize import extract_position_rank
        if "position_rank" in espn_df.columns:
            espn_df["position_rank"] = espn_df["position_rank"].apply(extract_position_rank)
        # --- Manual Mapping Integration ---
        from etl.transform.fetch_manual_mappings import fetch_manual_mappings_from_db
        from etl.transform.manual_mapping import apply_manual_mappings
        manual_mappings_df = fetch_manual_mappings_from_db()
        if not manual_mappings_df.empty:
            espn_df = apply_manual_mappings(espn_df, manual_mappings_df)
        logger.info(json.dumps({"event": "success", "step": "espn_pdf_extraction_2025"}))
        logger.info(json.dumps({"event": "data_sample", "step": "espn_etl_pdf_2025", "sample": espn_df.head().to_dict()}))
        load_normalized_source_to_db(espn_df, season=2025, source='ESPN_PDF_2025')
        logger.info(json.dumps({"event": "complete", "step": "espn_etl_pdf_2025"}))
    else:
        logger.error(json.dumps({"event": "failure", "step": "espn_pdf_extraction_2025", "error": "No data extracted from ESPN 2025 PDF."}))

if __name__ == "__main__":
    try:
        test_yahoo_etl()
        test_draftsharks_etl()
        # test_espn_etl() was undefined; ESPN PDF ETL is now run above as part of main flow
        logger.info(json.dumps({"event": "all_etl_completed"}))
    except Exception as e:
        stack = traceback.format_exc()
        logger.error(json.dumps({"event": "etl_failure", "error": str(e), "trace": stack}))
        notifier.send(f"ETL Failure: {e}\n```{stack}```")
        raise
