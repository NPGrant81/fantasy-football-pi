"""
Add source column to manual_player_mappings table (as TEXT, or alter if exists)
"""
revision = '0002_add_source_to_manual_player_mappings'
down_revision = '0001_create_draft_value_tables'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Use raw SQL to alter the column type if it exists, or add if not
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='manual_player_mappings' AND column_name='source';
    """))
    if result.fetchone():
        # Alter type to TEXT (Postgres syntax)
        op.execute(sa.text('ALTER TABLE manual_player_mappings ALTER COLUMN source TYPE TEXT;'))
    else:
        op.add_column('manual_player_mappings', sa.Column('source', sa.Text(), index=True))

def downgrade():
    op.drop_column('manual_player_mappings', 'source')
