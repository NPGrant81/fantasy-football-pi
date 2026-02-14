import models
# backend/utils/waiver_logic.py
def calculate_waiver_priority(league_id, db):
    """
    Returns a list of owners sorted by priority.
    Logic: Inverse of standings (last place gets #1 priority).
    """
    owners = db.query(models.User).filter(models.User.league_id == league_id).all()
    # Mock standings sort - in real test, this will use Win/Loss record
    sorted_owners = sorted(owners, key=lambda x: x.wins, reverse=False)
    return sorted_owners
