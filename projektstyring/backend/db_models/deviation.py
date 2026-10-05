from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
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


class Deviation(Base):
    """
    En afvigelse registreret på et projekt.

    Afvigelser er ikke en del af den normale produktionsplan.
    De opstår under projektets udførelse og repræsenterer arbejde,
    som skal følges indtil det er udført og eventuelt godkendt.

    C5 er den primære datakilde for afvigelsens livscyklus.
    """

    __tablename__ = "deviations"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "deviation_number",
            name="uq_deviations_project_number",
        ),
        Index(
            "ix_deviations_project_completed",
            "project_id",
            "completed_date",
        ),
        Index(
            "ix_deviations_project_approved",
            "project_id",
            "approved_date",
        ),
        Index(
            "ix_deviations_type",
            "deviation_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    deviation_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    installation_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "installations.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    bottom_manhole_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "manholes.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    top_manhole_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "manholes.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    dimension_mm: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    deviation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    reported_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    completed_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    completed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    approved_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="c5",
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
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

    project = relationship(
        "Project",
        back_populates="deviations",
    )

    installation = relationship(
        "Installation",
    )

    bottom_manhole = relationship(
        "Manhole",
        foreign_keys=[bottom_manhole_id],
    )

    top_manhole = relationship(
        "Manhole",
        foreign_keys=[top_manhole_id],
    )
