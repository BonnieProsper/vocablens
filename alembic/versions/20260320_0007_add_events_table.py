"""add centralized events table

Revision ID: 20260320_0007
Revises: 20260320_0006
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260320_0007"
down_revision = "20260320_0006"
branch_labels = None
depends_on = None


def _payload_type():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", _payload_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_events_user", "events", ["user_id", "created_at"])
    op.create_index("idx_events_type", "events", ["event_type", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_events_type", table_name="events")
    op.drop_index("idx_events_user", table_name="events")
    op.drop_table("events")
