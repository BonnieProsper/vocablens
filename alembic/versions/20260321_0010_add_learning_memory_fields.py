"""add learning memory fields to vocabulary

Revision ID: 20260321_0010
Revises: 20260320_0009
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260321_0010"
down_revision = "20260320_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("vocabulary") as batch_op:
        batch_op.add_column(sa.Column("last_seen_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("success_rate", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("decay_score", sa.Float(), nullable=False, server_default="0"))
        batch_op.create_index("idx_vocab_user_decay", ["user_id", "decay_score"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("vocabulary") as batch_op:
        batch_op.drop_index("idx_vocab_user_decay")
        batch_op.drop_column("decay_score")
        batch_op.drop_column("success_rate")
        batch_op.drop_column("last_seen_at")
