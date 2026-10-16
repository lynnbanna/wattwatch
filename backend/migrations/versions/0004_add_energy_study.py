"""Add energy study to analyses.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

JsonType = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("analyses", sa.Column("energy_study", JsonType, nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "energy_study")
