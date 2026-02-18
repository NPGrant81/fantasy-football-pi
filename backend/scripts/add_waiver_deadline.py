import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import engine
from sqlalchemy import text

# Add waiver_deadline column to league_settings if it does not exist
with engine.connect() as connection:
    # Check if column exists
    result = connection.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='league_settings' AND column_name='waiver_deadline'
    """))
    if not result.fetchone():
        connection.execute(text("ALTER TABLE league_settings ADD COLUMN waiver_deadline VARCHAR(255)"))
        connection.commit()
        print("✅ Success! 'waiver_deadline' column added to league_settings.")
    else:
        print("ℹ️ 'waiver_deadline' column already exists in league_settings.")
