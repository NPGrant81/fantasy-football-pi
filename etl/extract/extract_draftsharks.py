# Extract DraftSharks Fantasy Football Draft Data

"""
This script will connect to the DraftSharks ADP/Projections endpoint, fetch
draft value and projection data, and save the raw results for further
processing.

Two scrapers are provided:

1. scrape_draft_sharks_adp(url)  — PPR/superflex ADP table
   Default URL: https://www.draftsharks.com/adp/superflex/ppr/sleeper/12

2. scrape_draft_sharks_auction_values(season, league_size)  — Auction value table
   URL: https://www.draftsharks.com/auction-values
"""

import requests
import pandas as pd
from etl.transform.normalize import normalize_player_name, standardize_adp, extract_position_rank

AUCTION_VALUES_URL = "https://www.draftsharks.com/auction-values"

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    )
}


def _find_col(cols: list[str], *keywords: str) -> str | None:
    """Return the first column name that contains any of the given keywords."""
    for col in cols:
        for kw in keywords:
            if kw in col:
                return col
    return None


def scrape_draft_sharks_adp(url: str) -> pd.DataFrame:
    """
    Scrapes the public ADP table from Draft Sharks and returns it as a DataFrame.
    """
    print(f"Fetching data from: {url}...")
    try:
        response = requests.get(url, headers=_HEADERS, timeout=30)
        response.raise_for_status()
        tables = pd.read_html(response.text)
        if not tables:
            print("Error: No HTML tables found on the page.")
            return None
        adp_df = tables[0]
        adp_df.columns = [str(col).lower().replace(' ', '_') for col in adp_df.columns]
        return adp_df
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return None


def transform_draftsharks_adp(df: pd.DataFrame, league_size=12):
    """
    Normalize DraftSharks ADP DataFrame to standard schema.
    """
    normalized = []
    for _, row in df.iterrows():
        normalized.append({
            'normalized_name': normalize_player_name(row.get('player', '')),
            'position': row.get('pos', ''),
            'team': row.get('team', ''),
            'adp': standardize_adp(row.get('adp', ''), league_size=league_size),
            'raw_adp': row.get('adp', ''),
            'auction_value': row.get('auction', None),
            'bye_week': row.get('bye', None),
            'position_rank': extract_position_rank(row.get('pos_rank', '')),
            'raw_position_rank': row.get('pos_rank', None),
            # Add more fields as needed
        })
    return pd.DataFrame(normalized)


def scrape_draft_sharks_auction_values(
    url: str = AUCTION_VALUES_URL,
) -> pd.DataFrame | None:
    """
    Scrape the DraftSharks Auction Values page.

    Returns a raw DataFrame with lowercased, underscore-separated column names,
    or None on failure.

    Reference URL: https://www.draftsharks.com/auction-values
    """
    print(f"Fetching DraftSharks auction values from: {url}...")
    try:
        response = requests.get(url, headers=_HEADERS, timeout=30)
        response.raise_for_status()
        tables = pd.read_html(response.text)
        if not tables:
            print("Error: No HTML tables found on the page.")
            return None
        df = tables[0]
        df.columns = [str(col).lower().replace(' ', '_') for col in df.columns]
        return df
    except Exception as exc:
        print(f"An error occurred scraping auction values: {exc}")
        return None


def transform_draftsharks_auction_values(
    df: pd.DataFrame,
    league_size: int = 12,
) -> pd.DataFrame:
    """
    Normalize a raw DraftSharks Auction Values DataFrame into the standard
    schema required by load_normalized_source_to_db.

    Handles flexible column naming (the auction-values page may differ from the
    ADP page) using keyword-based column detection.

    Required output columns: normalized_name, position, team, adp
    Optional enrichment:     auction_value, projected_points, bye_week, position_rank
    """
    cols = list(df.columns)

    name_col = _find_col(cols, 'player', 'name', 'athlete')
    pos_col = _find_col(cols, 'pos', 'position')
    team_col = _find_col(cols, 'team', 'tm')
    auc_col = _find_col(cols, 'auction', 'value', 'bid')
    adp_col = _find_col(cols, 'adp', 'avg_pick', 'avg_draft')
    pts_col = _find_col(cols, 'proj', 'point', 'pts', 'fantasy')
    bye_col = _find_col(cols, 'bye')

    normalized = []
    for _, row in df.iterrows():
        raw_name = row.get(name_col, '') if name_col else ''
        raw_pos = str(row.get(pos_col, '')) if pos_col else ''
        raw_team = str(row.get(team_col, '')) if team_col else ''

        # Skip header-repeat rows (DraftSharks occasionally embeds them)
        if str(raw_name).lower() in ('player', 'name', ''):
            continue

        adp_raw = row.get(adp_col) if adp_col else None
        adp_val = standardize_adp(adp_raw, league_size=league_size) if adp_raw is not None else 0.0

        # Parse auction value — may be formatted as "$25" or "25"
        auction_raw = row.get(auc_col) if auc_col else None
        auction_val = None
        if auction_raw is not None:
            try:
                auction_val = float(str(auction_raw).replace('$', '').replace(',', '').strip())
            except (ValueError, TypeError):
                auction_val = None

        pts_raw = row.get(pts_col) if pts_col else None
        try:
            projected_points = float(pts_raw) if pts_raw is not None else None
        except (ValueError, TypeError):
            projected_points = None

        normalized.append({
            'normalized_name': normalize_player_name(str(raw_name)),
            'position': raw_pos.split('/')[0].strip().upper(),  # "RB/WR" → "RB"
            'team': raw_team.upper() if raw_team else '',
            'adp': adp_val,
            'auction_value': auction_val,
            'projected_points': projected_points,
            'bye_week': row.get(bye_col) if bye_col else None,
            'position_rank': extract_position_rank(raw_pos),
        })

    result = pd.DataFrame(normalized)
    result['adp'] = pd.to_numeric(result['adp'], errors='coerce').fillna(0.0)
    return result


if __name__ == "__main__":
    ds_url = "https://www.draftsharks.com/adp/superflex/ppr/sleeper/12"
    df = scrape_draft_sharks_adp(ds_url)
    if df is not None:
        print("\n--- Successfully Scraped ADP Data ---")
        print(f"Total Players Found: {len(df)}")
        print("\nPreview of the first 5 rows:")
        print(df.head())
        norm_df = transform_draftsharks_adp(df)
        print("\nNormalized DraftSharks ADP Data:")
        print(norm_df.head())
        # norm_df.to_csv('draftsharks_adp_normalized.csv', index=False)

    print("\n--- DraftSharks Auction Values ---")
    auc_df = scrape_draft_sharks_auction_values()
    if auc_df is not None:
        print(f"Total Players Found: {len(auc_df)}")
        print(auc_df.head())
        norm_auc = transform_draftsharks_auction_values(auc_df)
        print("\nNormalized:")
        print(norm_auc.head())
        # norm_auc.to_csv('draftsharks_auction_normalized.csv', index=False)
