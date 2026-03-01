"""merge efficiency and keeper heads

Revision ID: 5517dcbf0494
Revises: 0010_efficiency_details, 0012_add_keeper_max_years
Create Date: 2026-02-28 16:56:05.706101

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = '5517dcbf0494'
down_revision: Union[str, Sequence[str], None] = ('0010_efficiency_details', '0012_add_keeper_max_years')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
