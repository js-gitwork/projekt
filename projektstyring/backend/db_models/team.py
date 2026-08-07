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


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
        index=True,
    )

    calendar_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "work_calendars.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
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

    calendar = relationship(
        "WorkCalendar",
        back_populates="teams",
    )

    task_permissions = relationship(
        "TeamTaskPermission",
        back_populates="team",
        cascade="all, delete-orphan",
    )

    capacity_rates = relationship(
        "TeamCapacityRate",
        back_populates="team",
        cascade="all, delete-orphan",
    )

    task_assignments = relationship(
        "TaskAssignment",
        back_populates="team",
    )

    manhole_work_entries = relationship(
        "ManholeWork",
        back_populates="team",
    )

    service_connection_work_entries = relationship(
        "ServiceConnectionWork",
        back_populates="team",
    )

class TeamTaskPermission(Base):
    __tablename__ = "team_task_permissions"

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "task_type_id",
            name="uq_team_task_permissions_team_task_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    team_id: Mapped[str] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    task_type_id: Mapped[str] = mapped_column(
        ForeignKey(
            "task_types.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    valid_from: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    valid_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
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

    team = relationship(
        "Team",
        back_populates="task_permissions",
    )

    task_type = relationship(
        "TaskType",
    )


class TeamCapacityRate(Base):
    __tablename__ = "team_capacity_rates"

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "task_type_id",
            "quantity_type",
            name="uq_team_capacity_rates_team_task_quantity",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    team_id: Mapped[str] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    task_type_id: Mapped[str] = mapped_column(
        ForeignKey(
            "task_types.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    quantity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    capacity_per_day: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    unit: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    valid_from: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    valid_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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

    team = relationship(
        "Team",
        back_populates="capacity_rates",
    )

    task_type = relationship(
        "TaskType",
    )
