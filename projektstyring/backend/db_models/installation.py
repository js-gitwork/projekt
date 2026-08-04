from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from projektstyring.backend.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Installation(Base):
    __tablename__ = "installations"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "installation_no",
            name="uq_installations_project_installation_no",
        ),
        UniqueConstraint(
            "project_id",
            "sequence",
            name="uq_installations_project_sequence",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    installation_no: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Fastlægges manuelt på projektledermødet og fungerer
    # som planens anker for installationen.
    hoveddato: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    expected_stik: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    active_stik: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    opened_stik: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    langhatte: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    korthatte_extra: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    broende: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    bronde_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    hovedledning_meter: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
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
        back_populates="installations",
    )

    tasks = relationship(
        "ProjectTask",
        back_populates="installation",
    )

    progress = relationship(
        "InstallationProgress",
        back_populates="installation",
        cascade="all, delete-orphan",
        uselist=False,
    )

    stretches = relationship(
        "Stretch",
        back_populates="installation",
        cascade="all, delete-orphan",
        order_by="Stretch.sequence",
    )