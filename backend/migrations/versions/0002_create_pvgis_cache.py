"""Create PVGIS response cache.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

JsonType = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "pvgis_cache",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response", JsonType, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("pvgis_cache")
