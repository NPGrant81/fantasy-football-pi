# Extract DraftSharks Fantasy Football Draft Data

"""
This script will connect to the DraftSharks ADP/Projections endpoint, fetch draft value and projection data, and save the raw results for further processing.
"""

import requests
import pandas as pd
from etl.transform.normalize import normalize_player_name, standardize_adp, extract_position_rank

def scrape_draft_sharks_adp(url: str) -> pd.DataFrame:
    """
    Scrapes the public ADP table from Draft Sharks and returns it as a DataFrame.
    """
    print(f"Fetching data from: {url}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
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

if __name__ == "__main__":
    ds_url = "https://www.draftsharks.com/adp/superflex/ppr/sleeper/12"
    df = scrape_draft_sharks_adp(ds_url)
    if df is not None:
        print("\n--- Successfully Scraped Data ---")
        print(f"Total Players Found: {len(df)}")
        print("\nPreview of the first 5 rows:")
        print(df.head())
        norm_df = transform_draftsharks_adp(df)
        print("\nNormalized DraftSharks Data:")
        print(norm_df.head())
        # Optionally save
        # norm_df.to_csv('draftsharks_adp_normalized.csv', index=False)
