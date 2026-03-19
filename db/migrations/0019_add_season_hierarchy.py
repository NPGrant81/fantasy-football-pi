"""add season hierarchy: matchups.season/is_playoff, transaction_history.season, leagues.current_season, league_mfl_seasons table

Revision ID: 0019_add_season_hierarchy
Revises: 0018_add_mfl_ingestion_metadata_tables
Create Date: 2026-03-18

Summary of changes
------------------
* matchups.season (INTEGER, nullable)
    Calendar year of the season a matchup belongs to (e.g. 2007, 2024).
    Nullable for backward compatibility with any existing rows.
    All new rows — historical import and live-season — must populate this.

* matchups.is_playoff (BOOLEAN, default false)
    Distinguishes playoff-round matchups from regular-season weeks.

* Partial unique index uix_matchups_league_season_week_home
    ON matchups(league_id, season, week, home_team_id) WHERE season IS NOT NULL
    Fires only once season is set; zero-downtime against legacy NULL rows.
    Prevents duplicate imports and live-season double-writes.

* transaction_history.season (INTEGER, nullable)
    Same calendar-year anchor so trades/adds/drops can be queried per season.

* leagues.current_season (INTEGER, nullable)
    Tracks which season year is currently "live". One integer per league — the
    import pipeline and season-rollover logic can read this without inference.

* league_mfl_seasons (new table)
    Canonical mapping: (app league_id, season year) -> MFL numeric league ID.
    MFL assigns a brand-new league ID every season, so this table lets the
    import pipeline and season-rollover resolve the correct source without
    scanning fact rows. Unique on (league_id, season).
    Auto-seeded in this migration from existing mfl_html_record_facts data.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0019_add_season_hierarchy"
down_revision = "0018_add_mfl_ingestion_metadata_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. matchups — add season + is_playoff                               #
    # ------------------------------------------------------------------ #
    op.add_column("matchups", sa.Column("season", sa.Integer(), nullable=True))
    op.add_column(
        "matchups",
        sa.Column("is_playoff", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_matchups_season", "matchups", ["season"])

    # Partial unique index: only fires when season is populated.
    # NULL season rows (legacy / in-flight live rows) are exempt so the
    # migration is zero-downtime against any existing data.
    op.execute(
        """
        CREATE UNIQUE INDEX uix_matchups_league_season_week_home
        ON matchups (league_id, season, week, home_team_id)
        WHERE season IS NOT NULL
        """
    )

    # ------------------------------------------------------------------ #
    # 2. transaction_history — add season                                 #
    # ------------------------------------------------------------------ #
    op.add_column("transaction_history", sa.Column("season", sa.Integer(), nullable=True))
    op.create_index("ix_transaction_history_season", "transaction_history", ["season"])

    # ------------------------------------------------------------------ #
    # 3. leagues — add current_season                                     #
    # ------------------------------------------------------------------ #
    op.add_column("leagues", sa.Column("current_season", sa.Integer(), nullable=True))
    op.create_index("ix_leagues_current_season", "leagues", ["current_season"])

    # ------------------------------------------------------------------ #
    # 4. league_mfl_seasons — new table                                   #
    # ------------------------------------------------------------------ #
    op.create_table(
        "league_mfl_seasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        # MFL assigns a brand-new numeric league ID each season year
        sa.Column("mfl_league_id", sa.String(), nullable=False),
        sa.Column("mfl_franchise_count", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "season", name="uq_league_mfl_season"),
    )
    op.create_index("ix_league_mfl_seasons_id", "league_mfl_seasons", ["id"])
    op.create_index("ix_league_mfl_seasons_league_id", "league_mfl_seasons", ["league_id"])
    op.create_index("ix_league_mfl_seasons_season", "league_mfl_seasons", ["season"])

    # ------------------------------------------------------------------ #
    # 5. Seed league_mfl_seasons from existing HTML fact data             #
    # ------------------------------------------------------------------ #
    # Pull distinct (mfl_source_league_id, season_year) already mapped to
    # target leagues in mfl_ingestion_runs and insert them so the mapping
    # table is immediately useful without a separate seed step.
    op.execute(
        """
        INSERT INTO league_mfl_seasons (league_id, season, mfl_league_id, notes)
        SELECT DISTINCT ON (ir.target_league_id, f.season)
            ir.target_league_id,
            f.season,
            f.league_id,
            'seeded from mfl_html_record_facts on migration 0019'
        FROM (
            SELECT DISTINCT season, league_id
            FROM mfl_html_record_facts
            WHERE season IS NOT NULL AND league_id IS NOT NULL
        ) f
        CROSS JOIN (
            SELECT DISTINCT target_league_id
            FROM mfl_ingestion_runs
            WHERE target_league_id IS NOT NULL
        ) ir
        ORDER BY ir.target_league_id, f.season
        ON CONFLICT ON CONSTRAINT uq_league_mfl_season DO NOTHING
        """
    )


def downgrade() -> None:
    # 4
    op.drop_index("ix_league_mfl_seasons_season", table_name="league_mfl_seasons")
    op.drop_index("ix_league_mfl_seasons_league_id", table_name="league_mfl_seasons")
    op.drop_index("ix_league_mfl_seasons_id", table_name="league_mfl_seasons")
    op.drop_table("league_mfl_seasons")

    # 3
    op.drop_index("ix_leagues_current_season", table_name="leagues")
    op.drop_column("leagues", "current_season")

    # 2
    op.drop_index("ix_transaction_history_season", table_name="transaction_history")
    op.drop_column("transaction_history", "season")

    # 1
    op.execute("DROP INDEX IF EXISTS uix_matchups_league_season_week_home")
    op.drop_index("ix_matchups_season", table_name="matchups")
    op.drop_column("matchups", "is_playoff")
    op.drop_column("matchups", "season")
