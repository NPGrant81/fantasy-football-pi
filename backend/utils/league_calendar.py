# backend/utils/league_calendar.py
from datetime import datetime

def is_transaction_window_open():
    """
    Waivers/Trades usually process Wed 3AM. 
    This locks the system during game days (Thurs-Mon).
    """
    now = datetime.now()
    # 0=Monday, 1=Tuesday, 2=Wednesday...
    # Allow moves only between Wed 3AM and Thursday Kickoff
    if now.weekday() == 2 and now.hour >= 3:
        return True
    if now.weekday() in [3, 4, 5, 6, 0, 1]:
        return False
    return True
