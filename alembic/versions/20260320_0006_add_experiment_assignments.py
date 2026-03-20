"""add experiment assignments

Revision ID: 20260320_0006
Revises: 20260318_0005
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260320_0006"
down_revision = "20260318_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiment_assignments",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("experiment_key", sa.String(), nullable=False),
        sa.Column("variant", sa.String(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("user_id", "experiment_key", name="pk_experiment_assignments"),
    )
    op.create_index(
        "idx_experiment_assignments_variant",
        "experiment_assignments",
        ["experiment_key", "variant"],
    )
    op.create_index(
        "idx_experiment_assignments_assigned_at",
        "experiment_assignments",
        ["assigned_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_experiment_assignments_assigned_at", table_name="experiment_assignments")
    op.drop_index("idx_experiment_assignments_variant", table_name="experiment_assignments")
    op.drop_table("experiment_assignments")
