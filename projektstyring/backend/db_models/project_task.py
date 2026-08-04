from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
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


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    __table_args__ = (
        UniqueConstraint(
            "installation_id",
            "task_type_id",
            name="uq_project_tasks_installation_task_type",
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

    installation_id: Mapped[int | None] = mapped_column(
        ForeignKey("installations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    task_type_id: Mapped[str] = mapped_column(
        ForeignKey("task_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
    )

    scheduling_mode: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="calculated",
    )

    fixed_start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    earliest_start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="project",
    )

    metadata_data: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
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
        back_populates="tasks",
    )

    installation = relationship(
        "Installation",
        back_populates="tasks",
    )

    task_type = relationship(
        "TaskType",
        back_populates="tasks",
    )
    
    task_assignments = relationship(
        "TaskAssignment",
        back_populates="project_task",
        cascade="all, delete-orphan",
    )

    quantities = relationship(
        "TaskQuantity",
        back_populates="project_task",
        cascade="all, delete-orphan",
    )
