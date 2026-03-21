"""add canonical user state tables

Revision ID: 20260321_0011
Revises: 20260321_0010
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260321_0011"
down_revision = "20260321_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_learning_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("weak_areas", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("mastery_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_learning_states_user_id"),
    )
    op.create_index("idx_user_learning_states_user", "user_learning_states", ["user_id"], unique=False)
    op.create_index("idx_user_learning_states_updated_at", "user_learning_states", ["updated_at"], unique=False)

    op.create_table(
        "user_engagement_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("momentum_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_sessions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sessions_last_3_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_session_at", sa.DateTime(), nullable=True),
        sa.Column("shields_used_this_week", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_mission_completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_engagement_states_user_id"),
        sa.CheckConstraint("current_streak >= 0", name="ck_user_engagement_states_current_streak_nonnegative"),
        sa.CheckConstraint("longest_streak >= 0", name="ck_user_engagement_states_longest_streak_nonnegative"),
        sa.CheckConstraint("momentum_score >= 0 AND momentum_score <= 1", name="ck_user_engagement_states_momentum_score_range"),
        sa.CheckConstraint("total_sessions >= 0", name="ck_user_engagement_states_total_sessions_nonnegative"),
        sa.CheckConstraint("sessions_last_3_days >= 0", name="ck_user_engagement_states_sessions_last_3_days_nonnegative"),
        sa.CheckConstraint("shields_used_this_week >= 0", name="ck_user_engagement_states_shields_used_nonnegative"),
    )
    op.create_index("idx_user_engagement_states_user", "user_engagement_states", ["user_id"], unique=False)
    op.create_index("idx_user_engagement_states_updated_at", "user_engagement_states", ["updated_at"], unique=False)

    op.create_table(
        "user_progress_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("milestones", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_progress_states_user_id"),
        sa.CheckConstraint("xp >= 0", name="ck_user_progress_states_xp_nonnegative"),
        sa.CheckConstraint("level >= 1", name="ck_user_progress_states_level_min"),
    )
    op.create_index("idx_user_progress_states_user", "user_progress_states", ["user_id"], unique=False)
    op.create_index("idx_user_progress_states_updated_at", "user_progress_states", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_user_progress_states_updated_at", table_name="user_progress_states")
    op.drop_index("idx_user_progress_states_user", table_name="user_progress_states")
    op.drop_table("user_progress_states")

    op.drop_index("idx_user_engagement_states_updated_at", table_name="user_engagement_states")
    op.drop_index("idx_user_engagement_states_user", table_name="user_engagement_states")
    op.drop_table("user_engagement_states")

    op.drop_index("idx_user_learning_states_updated_at", table_name="user_learning_states")
    op.drop_index("idx_user_learning_states_user", table_name="user_learning_states")
    op.drop_table("user_learning_states")
