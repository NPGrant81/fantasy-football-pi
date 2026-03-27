# Extract ESPN Fantasy Football Draft Data

"""
This script will connect to the ESPN API, fetch draft value and projection data,
and save the raw results for further processing.

Two approaches are supported:

1. Public REST API (no credentials required):
   - scrape_espn_top_300(season, is_ppr) → Top 300 rankings + auction values
   - transform_espn_top_300(df) → normalized DataFrame

2. Authenticated via espn_api.football library (requires espn_s2/swid cookies):
   - fetch_espn_top300_with_auth(year, league_id, espn_s2, swid) → DataFrame
     with Projected Points in addition to rankings

   Obtain espn_s2 and swid from your browser cookies after logging into
   ESPN Fantasy.  They never expire unless you log out.
"""

import requests
import json
import pandas as pd
from etl.transform.normalize import normalize_player_name, extract_position_rank

# ESPN uses integer position IDs on the v3 REST API
ESPN_POSITION_MAP = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DEF"}


def scrape_espn_top_300(season: int = 2024, is_ppr: bool = True) -> pd.DataFrame:
    print(f"Fetching {season} ESPN Top 300 Rankings (PPR: {is_ppr})...")
    url = (
        f"https://fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
        "/segments/0/leaguedefaults/1?view=kona_player_info"
    )
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


def transform_espn_top_300(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the raw ESPN Top 300 DataFrame into the standard schema expected
    by load_normalized_source_to_db (requires normalized_name, position, team, adp).
    """
    normalized = []
    for _, row in df.iterrows():
        pos_id = row.get('position_id')
        position = ESPN_POSITION_MAP.get(int(pos_id), "UNK") if pos_id is not None else "UNK"
        # overall_rank used as a proxy for ADP (higher rank = lower ADP)
        raw_rank = row.get('overall_rank')
        adp_val = float(raw_rank) if raw_rank is not None else 0.0
        normalized.append({
            'espn_id': row.get('espn_id'),
            'normalized_name': normalize_player_name(row.get('scraped_player_name', '')),
            'position': position,
            'team': None,  # pro_team_id is a numeric code; leave None for name-based matching
            'adp': adp_val,
            'auction_value': row.get('auction_value'),
            'position_rank': extract_position_rank(position),
        })
    norm_df = pd.DataFrame(normalized)
    # Validation requires adp to be non-null numeric
    norm_df['adp'] = pd.to_numeric(norm_df['adp'], errors='coerce').fillna(0.0)
    norm_df['team'] = norm_df['team'].fillna('')
    return norm_df


def fetch_espn_top300_with_auth(
    year: int,
    league_id: int,
    espn_s2: str,
    swid: str,
    size: int = 300,
) -> pd.DataFrame | None:
    """
    Fetch Top 300 projected players using the espn_api.football library.
    Requires valid espn_s2 and swid browser cookies.

    Returns a normalized DataFrame compatible with load_normalized_source_to_db,
    or None on failure.
    """
    try:
        from espn_api.football import League  # type: ignore
    except ImportError:
        print("espn_api package not installed. Run: pip install espn_api")
        return None

    try:
        league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)
        players = league.free_agents(size=size)
    except Exception as exc:
        print(f"ESPN auth fetch failed: {exc}")
        return None

    rows = []
    for rank, player in enumerate(players, start=1):
        rows.append({
            'normalized_name': normalize_player_name(player.name),
            'position': str(player.position),
            'team': str(player.proTeam) if player.proTeam else None,
            'adp': float(rank),   # free_agents returns in projected-points order
            'projected_points': float(player.projected_total_points or 0),
            'auction_value': None,
        })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df['adp'] = pd.to_numeric(df['adp'], errors='coerce').fillna(0.0)
    df['team'] = df['team'].fillna('')
    return df


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
