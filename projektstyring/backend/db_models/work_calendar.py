from datetime import date, datetime, time, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from projektstyring.backend.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkCalendar(Base):
    __tablename__ = "work_calendars"

    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    timezone_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Europe/Copenhagen",
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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

    rules = relationship(
        "WorkCalendarRule",
        back_populates="calendar",
        cascade="all, delete-orphan",
        order_by="WorkCalendarRule.weekday",
    )

    exceptions = relationship(
        "CalendarException",
        back_populates="calendar",
        cascade="all, delete-orphan",
    )

    teams = relationship(
        "Team",
        back_populates="calendar",
    )


class WorkCalendarRule(Base):
    __tablename__ = "work_calendar_rules"

    __table_args__ = (
        UniqueConstraint(
            "calendar_id",
            "weekday",
            name="uq_work_calendar_rules_calendar_weekday",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    calendar_id: Mapped[str] = mapped_column(
        ForeignKey(
            "work_calendars.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # Python-standard:
    # 0 = mandag, 1 = tirsdag ... 6 = søndag.
    weekday: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    working: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    start_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )

    end_time: Mapped[time | None] = mapped_column(
        Time,
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

    calendar = relationship(
        "WorkCalendar",
        back_populates="rules",
    )


class CalendarException(Base):
    __tablename__ = "calendar_exceptions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    calendar_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "work_calendars.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    team_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    date_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    date_to: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    exception_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    working: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    start_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )

    end_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    decision_id: Mapped[int | None] = mapped_column(
        Integer,
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

    calendar = relationship(
        "WorkCalendar",
        back_populates="exceptions",
    )

    team = relationship(
        "Team",
    )
