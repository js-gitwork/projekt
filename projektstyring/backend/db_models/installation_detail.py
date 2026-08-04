from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from projektstyring.backend.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InstallationProgress(Base):
    __tablename__ = "installation_progress"

    installation_id: Mapped[int] = mapped_column(
        ForeignKey(
            "installations.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    # Felterne er nullable, fordi manglende C5-data
    # ikke må fortolkes som 0 procent.
    opmaaling: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    forarbejde: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    stikopmaaling: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    hovedledning: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    stikaabning: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="c5",
    )

    raw_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    imported_at: Mapped[datetime] = mapped_column(
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

    installation = relationship(
        "Installation",
        back_populates="progress",
    )


class Stretch(Base):
    __tablename__ = "stretches"

    __table_args__ = (
        UniqueConstraint(
            "installation_id",
            "sequence",
            name="uq_stretches_installation_sequence",
        ),
        Index(
            "ix_stretches_from_to_brond",
            "from_brond",
            "to_brond",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    installation_id: Mapped[int] = mapped_column(
        ForeignKey(
            "installations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    from_brond: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
    )

    to_brond: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
    )

    length_m: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    dimension: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
    )

    material: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
    )

    stik: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    metadata_data: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
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

    installation = relationship(
        "Installation",
        back_populates="stretches",
    )
