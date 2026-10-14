"""Database tables (SQLAlchemy). Schema changes go through Alembic migrations."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JsonType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    """One roof analysis: the stored image, what the model returned, and user corrections."""

    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    # SHA-256 of the file as uploaded; the stored image is a metadata-free PNG re-encoding.
    upload_sha256: Mapped[str] = mapped_column(String(64), index=True)
    image_key: Mapped[str] = mapped_column(String(128))
    model_name: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(32))
    # The full /roof-analysis response as the user first saw it.
    result: Mapped[dict[str, Any]] = mapped_column(JsonType)
    # User-corrected outlines and the areas measured from them; null until first edit.
    corrections: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    corrected_measurements: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
