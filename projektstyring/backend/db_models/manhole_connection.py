from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from projektstyring.backend.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ManholeConnection(Base):
    """En fysisk rørtilslutning i en brønd."""

    __tablename__ = "manhole_connections"

    __table_args__ = (
        CheckConstraint(
            "connection_type IN ('inlet', 'outlet')",
            name="ck_manhole_connections_type",
        ),
        CheckConstraint(
            "dimension_a_mm IS NULL OR dimension_a_mm > 0",
            name="ck_manhole_connections_dimension_a",
        ),
        CheckConstraint(
            "dimension_b_mm IS NULL OR dimension_b_mm > 0",
            name="ck_manhole_connections_dimension_b",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    manhole_id: Mapped[int] = mapped_column(
        ForeignKey("manholes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    connection_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    profile: Mapped[str] = mapped_column(
        String(50), nullable=False, default=""
    )

    dimension_a_mm: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    dimension_b_mm: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    material: Mapped[str] = mapped_column(
        String(50), nullable=False, default=""
    )

    notes: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    manhole = relationship("Manhole")
