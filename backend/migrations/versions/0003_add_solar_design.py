"""Add solar design to analyses.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

JsonType = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("analyses", sa.Column("solar_design", JsonType, nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "solar_design")
