"""add subscription trial fields

Revision ID: 20260320_0009
Revises: 20260320_0008
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260320_0009"
down_revision = "20260320_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.add_column(sa.Column("trial_started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("trial_ends_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("trial_tier", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_column("trial_tier")
        batch_op.drop_column("trial_ends_at")
        batch_op.drop_column("trial_started_at")
