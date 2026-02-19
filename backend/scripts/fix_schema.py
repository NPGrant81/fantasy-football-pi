from database import engine
from sqlalchemy import text

def run_safe(connection, statement, success_msg):
    try:
        connection.execute(text(statement))
        connection.commit()
        print(success_msg)
    except Exception as exc:
        connection.rollback()
        print(f"⚠️  Skipped: {exc}")


# Connect to the database
with engine.connect() as connection:
    # Existing fix
    run_safe(
        connection,
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN DEFAULT FALSE",
        "✅ Success! 'is_superuser' column added.",
    )

    # Add ESPN player id
    run_safe(
        connection,
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS espn_id VARCHAR UNIQUE",
        "✅ Success! 'espn_id' column added to players.",
    )

    # Weekly stats archive table
    run_safe(
        connection,
        """
        CREATE TABLE IF NOT EXISTS player_weekly_stats (
            id SERIAL PRIMARY KEY,
            player_id INTEGER REFERENCES players(id),
            season INTEGER,
            week INTEGER,
            fantasy_points DOUBLE PRECISION,
            stats JSON,
            source VARCHAR DEFAULT 'espn',
            created_at VARCHAR,
            CONSTRAINT uq_player_week_source UNIQUE (player_id, season, week, source)
        )
        """,
        "✅ Success! 'player_weekly_stats' table created.",
    )

    run_safe(
        connection,
        "ALTER TABLE bug_reports ADD COLUMN IF NOT EXISTS github_issue_url VARCHAR",
        "✅ Success! 'github_issue_url' column added to bug_reports.",
    )