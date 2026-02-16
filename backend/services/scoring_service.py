import pandas as pd
import nfl_data_py as nfl

# --- 1. THE MAPPING (Translating your IDs to Text) ---
# Your data uses "8002" for QB. We need to know that.
POSITION_MAP = {
    "QB": [8002],
    "RB": [8003],
    "WR": [8004],
    "TE": [8005],
    "DST": [8006],
    "K": [8099]
}

# --- 2. THE RULES (Your pasted data converted to a Dict) ---
# In the real app, this comes from your Database.
RULES = [
    # -- Big Play Bonuses --
    {"category": "passing_td_length", "min": 40, "max": 49, "points": 2, "positions": [8002]},
    {"category": "passing_td_length", "min": 50, "max": 99, "points": 3, "positions": [8002]},
    
    # -- Volume Ladders (Tiered Scoring) --
    {"category": "rushing_yards_total", "min": 100, "max": 109, "points": 5, "positions": [8003]},
    {"category": "rushing_yards_total", "min": 110, "max": 119, "points": 6, "positions": [8003]},
]

def calculate_score(player_id, player_position_code, week):
    """
    The Master Function that connects the dots.
    """
    total_score = 0
    breakdown = []

    # STEP 1: Get the RAW Data (The "Feed")
    # We fetch play-by-play data for the specific week
    pbp = nfl.import_pbp_data([2024]) # Using 2024 as placeholder
    week_data = pbp[pbp['week'] == week]
    
    # Filter for our specific player involved in the play
    # (Checking passer_id, rusher_id, or receiver_id)
    player_plays = week_data[
        (week_data['passer_player_id'] == player_id) | 
        (week_data['rusher_player_id'] == player_id) |
        (week_data['receiver_player_id'] == player_id)
    ]

    # STEP 2: Calculate "Event" Scores (The 40+ yard TD)
    # We loop through every single play this player touched the ball
    for index, play in player_plays.iterrows():
        
        # Check for Passing TD
        if play['pass_touchdown'] == 1 and play['passer_player_id'] == player_id:
            yards = play['yards_gained']
            
            # Check against our RULES list
            for rule in RULES:
                if rule['category'] == "passing_td_length":
                    if rule['min'] <= yards <= rule['max']:
                        total_score += rule['points']
                        breakdown.append(f"Pass TD of {yards} yds: +{rule['points']}")

    # STEP 3: Calculate "Volume" Scores (The 100+ Yard Game)
    # We sum up the total yards
    total_rushing = player_plays[player_plays['rusher_player_id'] == player_id]['yards_gained'].sum()
    
    for rule in RULES:
        if rule['category'] == "rushing_yards_total":
            if rule['min'] <= total_rushing <= rule['max']:
                total_score += rule['points']
                breakdown.append(f"Total Rushing ({total_rushing} yds): +{rule['points']}")

    return total_score, breakdown

# --- TESTING IT ---
# This simulates what happens when you click "Refresh Score"
if __name__ == "__main__":
    print("Fetching Data... (This takes a second because it's real NFL data)")
    # Note: You need a real player ID here. 
    # For now, I'm just showing you the logic structure.
    print("Logic Loaded. Ready to score.")
