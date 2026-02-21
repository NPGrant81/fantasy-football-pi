# Extract Yahoo Fantasy Football Draft Data

"""
This script connects to the Yahoo Fantasy API, fetches draft value and projection data, and saves the raw results for further processing.
"""

import pandas as pd
from yahoo_oauth import OAuth2
from etl.transform.normalize import normalize_player_name, standardize_adp, extract_position_rank

import os

def fetch_yahoo_top_players(max_players=100):
    # Always resolve oauth2.json relative to project root
    oauth_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'oauth2.json')
    oauth = OAuth2(None, None, from_file=oauth_path)
    top_players = []
    draft_positions = {"QB", "RB", "WR", "TE", "K", "DEF"}
    for start in range(0, max_players, 25):
        url = f"https://fantasysports.yahooapis.com/fantasy/v2/game/nfl/players;sort=ADP;start={start}?format=json"
        response = oauth.session.get(url)
        if response.status_code == 200:
            data = response.json()
            try:
                players_data = data['fantasy_content']['game'][1]['players']
                first_player_printed = False
                for key in players_data:
                    if key == 'count':
                        continue
                    player_info = players_data[key]['player']
                    if not first_player_printed:
                        import json
                        print("\nDEBUG: Raw player_info for first player:\n", json.dumps(player_info, indent=2)[:5000])
                        first_player_printed = True
                    info_list = player_info[0] if isinstance(player_info[0], list) else []
                    if not isinstance(info_list, list):
                        info_list = []
                    yahoo_id = None
                    name = None
                    position = None
                    nfl_team = None
                    bye_week = None
                    adp = None
                    auction_value = None
                    projected_points = None
                    eligible_positions = []
                    for entry in info_list:
                        if 'player_id' in entry:
                            yahoo_id = entry['player_id']
                        if 'name' in entry:
                            name = entry['name'].get('full')
                        if 'display_position' in entry:
                            position = entry['display_position']
                        if 'editorial_team_abbr' in entry:
                            nfl_team = entry['editorial_team_abbr']
                        if 'bye_weeks' in entry:
                            bye_week = entry['bye_weeks'].get('week')
                        if 'eligible_positions' in entry:
                            for pos in entry['eligible_positions']:
                                if 'position' in pos:
                                    eligible_positions.append(pos['position'])
                        if 'average_pick' in entry:
                            adp = entry['average_pick']
                        if 'auction_value' in entry:
                            auction_value = entry['auction_value']
                        if 'projected_points' in entry:
                            projected_points = entry['projected_points']
                    team_val = nfl_team.upper() if nfl_team else None
                    eligible_positions_str = ','.join(eligible_positions) if eligible_positions else None
                    # Only include players with a draft-relevant position
                    if position and any(pos in draft_positions for pos in position.split(",")):
                        top_players.append({
                            'YahooID': yahoo_id,
                            'Name': name,
                            'Position': position,
                            'Team': team_val,
                            'ByeWeek': bye_week,
                            'ADP': adp,
                            'AuctionValue': auction_value,
                            'ProjectedPoints': projected_points,
                            'EligiblePositions': eligible_positions_str
                        })
            except Exception as e:
                print("Reached the end of the available player list or encountered an unexpected JSON structure.")
                import json
                print("Full Yahoo API response:\n", json.dumps(data, indent=2)[:5000])
                print(f"Exception: {e}")
                break
        else:
            print(f"Failed to fetch data: {response.status_code}")
    return top_players

def transform_yahoo_players(players, league_size=12):
    """
    Normalize Yahoo player data for downstream processing.
    """
    normalized = []
    for p in players:
        position_rank = extract_position_rank(p.get('PositionRank', p['Position']))
        normalized.append({
            'yahoo_id': p.get('YahooID'),
            'normalized_name': normalize_player_name(p['Name']),
            'position': p['Position'],
            'team': p['Team'],
            'bye_week': p.get('ByeWeek'),
            'adp': standardize_adp(p['ADP'], league_size=league_size),
            'raw_adp': p['ADP'],
            'auction_value': p.get('AuctionValue'),
            'projected_points': p.get('ProjectedPoints'),
            'position_rank': position_rank,
            'raw_position_rank': p.get('PositionRank', None),
        })
    return normalized

if __name__ == "__main__":
    players = fetch_yahoo_top_players()
    df = pd.DataFrame(players)
    print("Raw Yahoo Data:")
    print(df.head(15))
    normalized = transform_yahoo_players(players)
    norm_df = pd.DataFrame(normalized)
    print("\nNormalized Yahoo Data:")
    print(norm_df.head(15))
    # Optionally save
    # norm_df.to_csv('yahoo_top_players_normalized.csv', index=False)
