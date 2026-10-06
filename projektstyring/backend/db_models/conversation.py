from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from projektstyring.backend.database.connection import Base


def create_conversation_key() -> str:
    return str(uuid4())


class ConversationState(Base):
    __tablename__ = "conversation_states"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_key: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )

    conversation_key: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        nullable=False,
        default=create_conversation_key,
    )

    title: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        default="Ny samtale",
    )

    kind: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="normal",
    )

    workflow: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )