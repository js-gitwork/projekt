from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from projektstyring.backend.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VPManholeNotificationSettings(Base):
    """
    Fælles indstillinger for VPManholes færdigmeldinger.

    Der skal kun eksistere én række med id=1.
    """

    __tablename__ = "vpmanhole_notification_settings"

    __table_args__ = (
        CheckConstraint(
            "id = 1",
            name="ck_vpmanhole_notification_settings_singleton",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    include_site_manager: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class VPManholeNotificationRecipient(Base):
    """
    En fast modtager valgt blandt systemets brugere.
    """

    __tablename__ = "vpmanhole_notification_recipients"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            name="uq_vpmanhole_notification_recipient_user",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class VPManholeNotificationEvent(Base):
    """
    Én færdigmelding pr. projekt.

    Status:
      pending  - venter på afsendelse
      sending  - afsendelse påbegyndt
      sent     - mailudbyderen har accepteret beskeden
      failed   - afsendelse fejlede
    """

    __tablename__ = "vpmanhole_notification_events"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            name="uq_vpmanhole_notification_event_project",
        ),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed')",
            name="ck_vpmanhole_notification_event_status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_vpmanhole_notification_attempt_count",
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
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    recipient_emails: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
