"""upgrade knowledge graph intelligence

Revision ID: 20260318_0004
Revises: 20260318_0003
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260318_0004"
down_revision = "20260318_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_graph_edges") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_knowledge_graph_edges_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("idx_kge_user_relation", ["user_id", "relation_type"])
        batch_op.create_index("idx_kge_user_target", ["user_id", "target_node"])
        batch_op.create_index("idx_kge_user_source", ["user_id", "source_node"])


def downgrade() -> None:
    with op.batch_alter_table("knowledge_graph_edges") as batch_op:
        batch_op.drop_index("idx_kge_user_source")
        batch_op.drop_index("idx_kge_user_target")
        batch_op.drop_index("idx_kge_user_relation")
        batch_op.drop_constraint("fk_knowledge_graph_edges_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")
