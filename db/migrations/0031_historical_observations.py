"""Separate reviewed historical auction evidence from live ownership."""

from alembic import op
import sqlalchemy as sa

revision = "0031_historical_observations"
down_revision = "0030_historical_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_auction_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "league_id", sa.Integer(), sa.ForeignKey("leagues.id"), nullable=False
        ),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_event_id", sa.String(128), nullable=False),
        sa.Column("league_mfl_id", sa.String(32), nullable=False),
        sa.Column("player_mfl_id", sa.String(32), nullable=False),
        sa.Column("franchise_id", sa.String(32), nullable=False),
        sa.Column("winning_bid", sa.Numeric(18, 6), nullable=False),
        sa.Column("position", sa.String(16), nullable=False),
        sa.Column("nfl_team", sa.String(16), nullable=True),
        sa.Column("team_labels", sa.JSON(), nullable=False),
        sa.Column("plan_sha256", sa.String(64), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "league_id",
            "source",
            "source_event_id",
            name="uq_historical_auction_source_event",
        ),
        sa.CheckConstraint("winning_bid >= 0", name="ck_historical_auction_bid"),
        sa.CheckConstraint(
            "length(trim(source)) > 0 AND length(trim(source_event_id)) > 0",
            name="ck_historical_auction_source_identity",
        ),
    )
    op.create_index(
        "ix_historical_auction_league_season",
        "historical_auction_observations",
        ["league_id", "season"],
    )


def downgrade() -> None:
    raise RuntimeError(
        "Historical observations are forward-only; restore a verified backup."
    )
