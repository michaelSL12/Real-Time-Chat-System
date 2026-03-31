"""add nickname to room members

Revision ID: ffa845ee52ac
Revises: cab26820ec07
Create Date: 2026-03-15 13:27:00.828945

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ffa845ee52ac'
down_revision: Union[str, Sequence[str], None] = 'cab26820ec07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "room_members",
        sa.Column("nickname", sa.String(length=50), nullable=True),
    )


def downgrade():
    op.drop_column("room_members", "nickname")