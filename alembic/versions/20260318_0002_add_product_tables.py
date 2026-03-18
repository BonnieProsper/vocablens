"""add monetization and personalization tables

Revision ID: 20260318_0002
Revises: 20260317_0001
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260318_0002"
down_revision = "20260317_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tokens_used >= 0", name="ck_usage_logs_tokens_used_nonnegative"),
    )
    op.create_index("idx_usage_user_day", "usage_logs", ["user_id", "created_at"])
    op.create_index("idx_usage_endpoint", "usage_logs", ["endpoint"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tier", sa.String(), nullable=False, server_default="free"),
        sa.Column("request_limit", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("token_limit", sa.Integer(), nullable=False, server_default="50000"),
        sa.Column("renewed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_subscriptions_user_id"),
        sa.CheckConstraint("request_limit >= 0", name="ck_subscriptions_request_limit_nonnegative"),
        sa.CheckConstraint("token_limit >= 0", name="ck_subscriptions_token_limit_nonnegative"),
    )
    op.create_index("idx_subscription_user", "subscriptions", ["user_id"])
    op.create_index("idx_subscription_renewed_at", "subscriptions", ["renewed_at"])

    op.create_table(
        "mistake_patterns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "category", "pattern", name="uq_mistake_patterns_user_category_pattern"),
        sa.CheckConstraint("count >= 1", name="ck_mistake_patterns_count_positive"),
    )
    op.create_index("idx_mistake_user_category", "mistake_patterns", ["user_id", "category"])
    op.create_index("idx_mistake_user_last_seen", "mistake_patterns", ["user_id", "last_seen_at"])

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learning_speed", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("retention_rate", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("difficulty_preference", sa.String(), nullable=False, server_default="medium"),
        sa.Column("content_preference", sa.String(), nullable=False, server_default="mixed"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
        sa.CheckConstraint("learning_speed > 0", name="ck_user_profiles_learning_speed_positive"),
        sa.CheckConstraint(
            "retention_rate >= 0 AND retention_rate <= 1",
            name="ck_user_profiles_retention_rate_range",
        ),
    )
    op.create_index("idx_user_profile_user", "user_profiles", ["user_id"])
    op.create_index("idx_user_profile_updated_at", "user_profiles", ["updated_at"])


def downgrade() -> None:
    op.drop_index("idx_user_profile_updated_at", table_name="user_profiles")
    op.drop_index("idx_user_profile_user", table_name="user_profiles")
    op.drop_table("user_profiles")

    op.drop_index("idx_mistake_user_last_seen", table_name="mistake_patterns")
    op.drop_index("idx_mistake_user_category", table_name="mistake_patterns")
    op.drop_table("mistake_patterns")

    op.drop_index("idx_subscription_renewed_at", table_name="subscriptions")
    op.drop_index("idx_subscription_user", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("idx_usage_endpoint", table_name="usage_logs")
    op.drop_index("idx_usage_user_day", table_name="usage_logs")
    op.drop_table("usage_logs")
