"""Create analyses table.

Revision ID: 0001
Revises:
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JsonType = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("upload_sha256", sa.String(64), nullable=False),
        sa.Column("image_key", sa.String(128), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("result", JsonType, nullable=False),
        sa.Column("corrections", JsonType, nullable=True),
        sa.Column("corrected_measurements", JsonType, nullable=True),
    )
    op.create_index("ix_analyses_upload_sha256", "analyses", ["upload_sha256"])


def downgrade() -> None:
    op.drop_index("ix_analyses_upload_sha256", table_name="analyses")
    op.drop_table("analyses")
