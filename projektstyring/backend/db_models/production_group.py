from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
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


class ProductionGroup(Base):
    __tablename__ = "production_groups"

    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
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

    task_type_members = relationship(
        "ProductionGroupTaskType",
        back_populates="production_group",
        cascade="all, delete-orphan",
    )

    work_type_members = relationship(
        "ProductionGroupWorkType",
        back_populates="production_group",
        cascade="all, delete-orphan",
    )


class ProductionGroupTaskType(Base):
    __tablename__ = "production_group_task_types"

    __table_args__ = (
        UniqueConstraint(
            "production_group_id",
            "task_type_id",
            name=(
                "uq_production_group_task_types_"
                "group_task_type"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    production_group_id: Mapped[str] = mapped_column(
        ForeignKey(
            "production_groups.id",
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

    production_group = relationship(
        "ProductionGroup",
        back_populates="task_type_members",
    )

    task_type = relationship(
        "TaskType",
    )


class ProductionGroupWorkType(Base):
    __tablename__ = "production_group_work_types"

    __table_args__ = (
        UniqueConstraint(
            "production_group_id",
            "work_type",
            name=(
                "uq_production_group_work_types_"
                "group_work_type"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    production_group_id: Mapped[str] = mapped_column(
        ForeignKey(
            "production_groups.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    work_type: Mapped[str] = mapped_column(
        String(50),
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

    production_group = relationship(
        "ProductionGroup",
        back_populates="work_type_members",
    )
