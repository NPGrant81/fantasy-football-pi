import pandas as pd
from backend.models import ManualPlayerMapping
from backend.database import SessionLocal

def fetch_manual_mappings_from_db() -> pd.DataFrame:
    session = SessionLocal()
    mappings = session.query(ManualPlayerMapping).all()
    session.close()
    # Convert to DataFrame
    data = [
        {
            'source_name': m.source,
            'scraped_player_name': m.scraped_name,
            'true_player_id': m.player_id,
            'team': m.team,
            'position': m.position,
            'notes': m.notes
        }
        for m in mappings
    ]
    return pd.DataFrame(data)
