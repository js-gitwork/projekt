from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from projektstyring.backend.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """
    Bruger med adgang til Projektstyring og VPManhole.

    Roller:
    - felt: feltarbejde og VPManhole
    - kontor: Projektstyring/Rørbot og VPManhole
    - admin: fuld adgang og brugeradministration
    """

    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('felt', 'kontor', 'admin')",
            name="ck_users_role",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        default="",
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
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
