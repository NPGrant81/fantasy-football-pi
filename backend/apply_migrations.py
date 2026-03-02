"""Run migrations for team visual assets and game status."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect, text
from backend.database import SQLALCHEMY_DATABASE_URL

engine = create_engine(SQLALCHEMY_DATABASE_URL)
inspector = inspect(engine)

user_cols = {c['name'] for c in inspector.get_columns('users')}
matchup_cols = {c['name'] for c in inspector.get_columns('matchups')}

with engine.begin() as conn:
    if 'team_logo_url' not in user_cols:
        print("Adding team visual fields...")
        conn.execute(text("ALTER TABLE users ADD COLUMN team_logo_url VARCHAR"))
        conn.execute(text("ALTER TABLE users ADD COLUMN team_color_primary VARCHAR DEFAULT '#3b82f6'"))
        conn.execute(text("ALTER TABLE users ADD COLUMN team_color_secondary VARCHAR DEFAULT '#1e40af'"))
        print("✓ Team visual fields added")
    
    if 'game_status' not in matchup_cols:
        print("Adding game_status field...")
        conn.execute(text("ALTER TABLE matchups ADD COLUMN game_status VARCHAR NOT NULL DEFAULT 'NOT_STARTED'"))
        print("✓ game_status field added")

print("Migrations complete!")
