from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from projektstyring.backend.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Manhole(Base):
    """
    En fysisk brønd i et projekt.

    Brøndnummeret er entydigt inden for projektet, men kan forekomme
    igen i et andet projekt.
    """

    __tablename__ = "manholes"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "manhole_no",
            name="uq_manholes_project_manhole_no",
        ),
        Index(
            "ix_manholes_project_active",
            "project_id",
            "active",
        ),
        CheckConstraint(
            "diameter_m IS NULL OR diameter_m >= 0",
            name="ck_manholes_diameter_non_negative",
        ),
        CheckConstraint(
            "depth_m IS NULL OR depth_m >= 0",
            name="ck_manholes_depth_non_negative",
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

    manhole_no: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    diameter_m: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )

    depth_m: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )

    profile: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
    )

    material: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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
        back_populates="manholes",
    )

    bottom_stretches = relationship(
        "Stretch",
        foreign_keys="Stretch.bottom_manhole_id",
        back_populates="bottom_manhole",
    )

    top_stretches = relationship(
        "Stretch",
        foreign_keys="Stretch.top_manhole_id",
        back_populates="top_manhole",
    )

    work_entries = relationship(
        "ManholeWork",
        back_populates="manhole",
        order_by="ManholeWork.created_at",
    )


class ManholeWork(Base):
    """
    En historisk registrering af planlagt eller udført arbejde på en brønd.

    Eksisterende poster skal normalt ikke overskrives eller slettes.
    Rettelser registreres som nye poster, eventuelt med reference til
    den post, de erstatter.
    """

    __tablename__ = "manhole_work"

    __table_args__ = (
        Index(
            "ix_manhole_work_type_status",
            "work_type",
            "status",
        ),
        Index(
            "ix_manhole_work_performed_date",
            "performed_date",
        ),
        CheckConstraint(
            "quantity >= 0",
            name="ck_manhole_work_quantity_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    manhole_id: Mapped[int] = mapped_column(
        ForeignKey(
            "manholes.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    decision_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "decisions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    supersedes_work_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "manhole_work.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    work_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="planned",
        index=True,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        default=Decimal("1"),
    )

    unit: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="stk",
    )

    performed_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    performed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    team_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="system",
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

    manhole = relationship(
        "Manhole",
        back_populates="work_entries",
    )

    decision = relationship(
        "Decision",
    )

    team = relationship(
        "Team",
        back_populates="manhole_work_entries",
    )

    supersedes_work = relationship(
        "ManholeWork",
        remote_side="ManholeWork.id",
    )


class ServiceConnection(Base):
    """
    Et fysisk stik på et bestemt stræk.

    external_id er DANDAS-identiteten, eksempelvis:

        4612022-4612023-18.40-2

    Hvis placering eller urretning ændres, er der tale om et nyt fysisk stik
    med en ny identitet.
    """

    __tablename__ = "service_connections"

    __table_args__ = (
        UniqueConstraint(
            "stretch_id",
            "position_m",
            "clock_position",
            name="uq_service_connections_stretch_position_clock",
        ),
        UniqueConstraint(
            "stretch_id",
            "external_id",
            name="uq_service_connections_stretch_external_id",
        ),
        Index(
            "ix_service_connections_status",
            "active",
            "to_be_opened",
            "decommissioned",
        ),
        CheckConstraint(
            "position_m >= 0",
            name="ck_service_connections_position_non_negative",
        ),
        CheckConstraint(
            "dimension_mm IS NULL OR dimension_mm > 0",
            name="ck_service_connections_dimension_positive",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    stretch_id: Mapped[int] = mapped_column(
        ForeignKey(
            "stretches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    external_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    position_m: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    clock_position: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    dimension_mm: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    material: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    to_be_opened: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    decommissioned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
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

    stretch = relationship(
        "Stretch",
        back_populates="service_connections",
    )

    work_entries = relationship(
        "ServiceConnectionWork",
        back_populates="service_connection",
        order_by="ServiceConnectionWork.created_at",
    )


class ServiceConnectionWork(Base):
    """
    En historisk registrering af arbejde på et stik.

    Arbejdstypen er data og ikke en databasekolonne. Eksempler:

    - langhat
    - korthat
    - raaskud
    - broendskud
    - punktreparation
    - partliner
    - omega
    """

    __tablename__ = "service_connection_work"

    __table_args__ = (
        Index(
            "ix_service_connection_work_type_status",
            "work_type",
            "status",
        ),
        Index(
            "ix_service_connection_work_performed_date",
            "performed_date",
        ),
        CheckConstraint(
            "quantity >= 0",
            name="ck_service_connection_work_quantity_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    service_connection_id: Mapped[int] = mapped_column(
        ForeignKey(
            "service_connections.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    decision_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "decisions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    supersedes_work_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "service_connection_work.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    work_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="planned",
        index=True,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        default=Decimal("1"),
    )

    unit: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="stk",
    )

    performed_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    performed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    team_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="system",
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

    service_connection = relationship(
        "ServiceConnection",
        back_populates="work_entries",
    )

    decision = relationship(
        "Decision",
    )

    team = relationship(
        "Team",
        back_populates="service_connection_work_entries",
    )

    supersedes_work = relationship(
        "ServiceConnectionWork",
        remote_side="ServiceConnectionWork.id",
    )
