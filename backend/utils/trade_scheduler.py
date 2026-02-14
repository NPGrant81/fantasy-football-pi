# backend/utils/trade_scheduler.py
from datetime import datetime

def is_player_locked(player_id, game_time):
    """
    Checks if a player is ineligible for trade/waivers 
    because their game is in progress or finished.
    """
    now = datetime.now()
    if now >= game_time:
        return True # Player is locked until Tuesday cycle
    return False
