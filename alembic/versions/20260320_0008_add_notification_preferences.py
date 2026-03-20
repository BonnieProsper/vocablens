"""add notification preferences to user profiles

Revision ID: 20260320_0008
Revises: 20260320_0007
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260320_0008"
down_revision = "20260320_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_profiles") as batch_op:
        batch_op.add_column(
            sa.Column("preferred_channel", sa.String(), nullable=False, server_default="push"),
        )
        batch_op.add_column(
            sa.Column("preferred_time_of_day", sa.Integer(), nullable=False, server_default="18"),
        )
        batch_op.add_column(
            sa.Column("frequency_limit", sa.Integer(), nullable=False, server_default="2"),
        )
        batch_op.create_check_constraint(
            "ck_user_profiles_preferred_channel_valid",
            "preferred_channel IN ('email', 'push', 'in_app')",
        )
        batch_op.create_check_constraint(
            "ck_user_profiles_preferred_time_of_day_range",
            "preferred_time_of_day >= 0 AND preferred_time_of_day <= 23",
        )
        batch_op.create_check_constraint(
            "ck_user_profiles_frequency_limit_nonnegative",
            "frequency_limit >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("user_profiles") as batch_op:
        batch_op.drop_constraint("ck_user_profiles_frequency_limit_nonnegative", type_="check")
        batch_op.drop_constraint("ck_user_profiles_preferred_time_of_day_range", type_="check")
        batch_op.drop_constraint("ck_user_profiles_preferred_channel_valid", type_="check")
        batch_op.drop_column("frequency_limit")
        batch_op.drop_column("preferred_time_of_day")
        batch_op.drop_column("preferred_channel")
