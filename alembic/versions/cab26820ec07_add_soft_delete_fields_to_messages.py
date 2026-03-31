"""add soft delete fields to messages

Revision ID: cab26820ec07
Revises: 73f3fb87b839
Create Date: 2026-03-15 12:47:05.072060
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cab26820ec07"
down_revision: Union[str, Sequence[str], None] = "73f3fb87b839"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("deleted_by_user_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_messages_deleted_by_user_id_users",
            "users",
            ["deleted_by_user_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_constraint(
            "fk_messages_deleted_by_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("deleted_by_user_id")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")