"""Add connections table and connection_id to query_log.

Revision ID: 001_add_connections
Revises:
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001_add_connections"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("database_url", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column(
        "query_log",
        sa.Column("connection_id", UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("query_log", "connection_id")
    op.drop_table("connections")
