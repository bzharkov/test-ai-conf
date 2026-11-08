"""catalog, requests, builds, chat tables

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "components",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("brand", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("specs", JSONB, nullable=False),
        sa.Column("perf_score", sa.Float),
        sa.Column("perf_multicore", sa.Float),
        sa.Column("perf_estimated", sa.Boolean, server_default=sa.false()),
        sa.Column("price_rub", sa.Numeric),
        sa.Column("in_stock", sa.Boolean, server_default=sa.false()),
        sa.Column("price_source", sa.Text),
        sa.Column("price_updated_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_ref", sa.Text),
        sa.Column("embedding", Vector(384)),
        sa.Column("search_text", sa.Text),
        sa.UniqueConstraint("category", "brand", "model", name="uq_component_identity"),
    )
    op.create_index("ix_components_category", "components", ["category"])
    op.create_index("ix_components_specs", "components", ["specs"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX ix_components_embedding ON components "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_table(
        "requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False, index=True),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("parsed_requirements", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "builds",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_id", sa.Integer, sa.ForeignKey("requests.id")),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("items", JSONB, nullable=False),
        sa.Column("total_price", sa.Numeric, nullable=False),
        sa.Column("estimated_power_w", sa.Float, nullable=False),
        sa.Column("psu_recommended_w", sa.Integer, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("explanation", sa.Text),
        sa.Column("warnings", JSONB, nullable=False),
        sa.Column("extra", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("build_id", sa.Integer, sa.ForeignKey("builds.id"), nullable=False, index=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for t in ("chat_messages", "builds", "requests", "components"):
        op.drop_table(t)
