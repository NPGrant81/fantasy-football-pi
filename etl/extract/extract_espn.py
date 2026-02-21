# Extract ESPN Fantasy Football Draft Data

"""
This script will connect to the ESPN API, fetch draft value and projection data, and save the raw results for further processing.
"""

import requests
import json
import pandas as pd
from etl.transform.normalize import normalize_player_name, standardize_adp, extract_position_rank

def scrape_espn_top_300(season: int = 2024, is_ppr: bool = True) -> pd.DataFrame:
    print(f"Fetching {season} ESPN Top 300 Rankings (PPR: {is_ppr})...")
    url = f"https://fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leaguedefaults/1?view=kona_player_info"
    scoring_type = "PPR" if is_ppr else "STANDARD"
    x_fantasy_filter = {
        "players": {
            "limit": 400,
            "sortDraftRanks": {
                "sortPriority": 100,
                "sortAsc": True,
                "value": scoring_type
            }
        }
    }
    headers = {'x-fantasy-filter': json.dumps(x_fantasy_filter)}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        player_list = []
        for p in data.get('players', []):
            player_info = p.get('player', {})
            player_id = player_info.get('id')
            full_name = player_info.get('fullName')
            pro_team_id = player_info.get('proTeamId')
            position_id = player_info.get('defaultPositionId')
            ranks = player_info.get('draftRanksByRankType', {}).get(scoring_type, {})
            overall_rank = ranks.get('rank')
            auction_value = ranks.get('auctionValue')
            if overall_rank and overall_rank <= 300:
                player_list.append({
                    'source_name': 'ESPN',
                    'espn_id': player_id,
                    'scraped_player_name': full_name,
                    'position_id': position_id,
                    'pro_team_id': pro_team_id,
                    'overall_rank': overall_rank,
                    'auction_value': auction_value
                })
        df = pd.DataFrame(player_list)
        df = df.sort_values(by='overall_rank').reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Error fetching ESPN data: {e}")
        return None

def transform_espn_top_300(df: pd.DataFrame):
    normalized = []
    for _, row in df.iterrows():
        normalized.append({
            'espn_id': row.get('espn_id'),
            'normalized_name': normalize_player_name(row.get('scraped_player_name', '')),
            'position_id': row.get('position_id'),
            'pro_team_id': row.get('pro_team_id'),
            'overall_rank': row.get('overall_rank'),
            'auction_value': row.get('auction_value'),
            # Add more fields as needed
        })
    return pd.DataFrame(normalized)

if __name__ == "__main__":
    espn_df = scrape_espn_top_300(season=2024, is_ppr=True)
    if espn_df is not None:
        print("\n--- Successfully Fetched ESPN Data ---")
        print(f"Total Players Found: {len(espn_df)}")
        print("\nTop 5 Players:")
        print(espn_df.head())
        norm_df = transform_espn_top_300(espn_df)
        print("\nNormalized ESPN Data:")
        print(norm_df.head())
        # Optionally save
        # norm_df.to_csv('espn_top_300_normalized.csv', index=False)
