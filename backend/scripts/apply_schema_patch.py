from sqlalchemy import text

from backend.database import engine


def main() -> None:
    with engine.connect() as conn:
        print("Applying league_settings and scoring_rules patch...")
        conn.execute(
            text(
                "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS playoff_qualifiers INTEGER DEFAULT 6"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS playoff_reseed BOOLEAN DEFAULT FALSE"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS playoff_consolation BOOLEAN DEFAULT TRUE"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE league_settings ADD COLUMN IF NOT EXISTS playoff_tiebreakers JSON DEFAULT '[\"overall_record\",\"head_to_head\",\"points_for\",\"points_against\",\"random_draw\"]'"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS category VARCHAR(50)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS event_name VARCHAR(100)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS description VARCHAR(255)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS range_min NUMERIC(10,2) DEFAULT 0"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS range_max NUMERIC(10,2) DEFAULT 9999.99"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS point_value NUMERIC(10,2)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS calculation_type VARCHAR(50) DEFAULT 'flat_bonus'"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS applicable_positions JSON DEFAULT '[\"ALL\"]'"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
            )
        )
        conn.commit()
        print("Patch applied")


if __name__ == "__main__":
    main()