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


class ProjectConstraint(Base):
    """
    En projektmæssig frist eller rådighedsperiode.

    Modellen bruges som faktagrundlag for Rørbot og andre
    overvågningsfunktioner. Den er ikke en del af den normale
    planlægningsmotor.

    Eksempler:
    - availability_permit
    - project_deadline
    """

    __tablename__ = "project_constraints"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "constraint_type",
            "reference",
            name="uq_project_constraints_project_type_reference",
        ),
        Index(
            "ix_project_constraints_project_type",
            "project_id",
            "constraint_type",
        ),
        Index(
            "ix_project_constraints_project_end_date",
            "project_id",
            "end_date",
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

    constraint_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
    )

    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manual",
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
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

    project = relationship(
        "Project",
        back_populates="constraints",
    )
