from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from projektstyring.backend.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VPManholeDelivery(Base):
    """
    Én billedaflevering pr. fysisk brønd.

    Brønden kan indgå i flere installationer, men dens
    billeder og afleveringsstatus gemmes kun én gang.
    """

    __tablename__ = "vpmanhole_deliveries"

    __table_args__ = (
        UniqueConstraint(
            "manhole_id",
            name="uq_vpmanhole_deliveries_manhole",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    manhole_id: Mapped[int] = mapped_column(
        ForeignKey("manholes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Fast installation til mappenavnet, fx "103 Inst. 3".
    folder_installation_id: Mapped[int] = mapped_column(
        ForeignKey("installations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    completed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
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


class VPManholePhoto(Base):
    """
    Metadata om et billede.

    Selve billedfilen gemmes på disk, ikke i PostgreSQL.
    """

    __tablename__ = "vpmanhole_photos"

    __table_args__ = (
        UniqueConstraint(
            "delivery_id",
            "photo_type",
            "sequence",
            name="uq_vpmanhole_photos_slot",
        ),
        CheckConstraint(
            "photo_type IN ('before', 'during', 'after', 'cover')",
            name="ck_vpmanhole_photos_type",
        ),
        CheckConstraint(
            "sequence >= 1",
            name="ck_vpmanhole_photos_sequence",
        ),
        CheckConstraint(
            "(photo_type = 'during') OR (sequence = 1)",
            name="ck_vpmanhole_photos_single_sequence",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    delivery_id: Mapped[int] = mapped_column(
        ForeignKey(
            "vpmanhole_deliveries.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    photo_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # Relativ filsti inden for det konfigurerede billedlager.
    relative_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
