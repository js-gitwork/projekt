
"""
Rørbots permanente videnskatalog.

FORMÅL
------
Gemmer verificerbar viden om datakilder, relationer,
feltbetydninger og genanvendelige undersøgelsesmetoder.

ARKITEKTUR
----------
Denne komponent tilhører Projektstyrings PostgreSQL-database.
Den er uafhængig af både AI-leverandør og ERP-system.

Kataloget indeholder metadata og undersøgelsesresultater,
ikke kopier af de eksterne systemers driftsdata.

SIKKERHED
---------
AI-modellen må ikke skrive direkte til disse tabeller.
Alle ændringer skal ske gennem et repository og en service,
som håndhæver verificeringsregler og adgangsrettigheder.

STATUS
------
Datamodel til den nye KnowledgeCatalog-komponent.
Endnu ikke tilsluttet Rørbots aktive produktionspipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from projektstyring.backend.database.connection import Base


def utc_now() -> datetime:
    """Returner et tidszonemarkeret UTC-tidspunkt."""
    return datetime.now(timezone.utc)


class KnowledgeSource(Base):
    """
    Identificerer en ekstern eller intern datakilde.

    source_key er en stabil teknisk identifikator, eksempelvis
    et konfigurationsnavn. Den må ikke indeholde adgangskoder.

    En datakilde er ikke nødvendigvis en hel database.
    Det kan også være et API eller et andet autoriseret system.
    """

    __tablename__ = "knowledge_sources"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    source_key: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )

    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )

    schema_fingerprint: Mapped[str | None] = mapped_column(
        String(128), nullable=True
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

    entries: Mapped[list["KnowledgeEntry"]] = relationship(
        back_populates="source"
    )


class KnowledgeEntry(Base):
    """
    Ét stykke genanvendelig viden om en datakilde.

    knowledge_type kan eksempelvis være:
    - relationship
    - field_meaning
    - investigation_method

    knowledge_key identificerer emnet stabilt inden for
    den pågældende kilde. Selve beskrivelsen ligger i
    definition, der skal valideres af servicelaget.

    verification_status skelner mellem:
    - discovered
    - technically_verified
    - business_verified
    - deprecated

    En AI-påstand må ikke automatisk løftes til
    technically_verified eller business_verified.

    definition er deklarative data, aldrig Python-kode,
    SQL-fragmenter til fri udførelse eller instruktioner.
    """

    __tablename__ = "knowledge_entries"

    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "knowledge_key",
            name="uq_knowledge_source_key",
        ),
        Index(
            "ix_knowledge_source_type_status",
            "source_id",
            "knowledge_type",
            "verification_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey(
            "knowledge_sources.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    knowledge_key: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    knowledge_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )

    definition: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    verification_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="discovered",
    )

    schema_fingerprint: Mapped[str | None] = mapped_column(
        String(128), nullable=True
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

    source: Mapped["KnowledgeSource"] = relationship(
        back_populates="entries"
    )

    evidence: Mapped[list["KnowledgeEvidence"]] = relationship(
        back_populates="entry"
    )


class KnowledgeEvidence(Base):
    """
    Dokumenterer én undersøgelse af en vidensregistrering.

    Testomfanget gemmes særskilt fra konklusionen.

    Eksempel:
    En relation kan give 29 match af 29 på ét projekt.
    Det dokumenterer konsistens inden for dette projekt,
    ikke nødvendigvis for hele ERP-databasen.

    outcome beskriver undersøgelsesresultatet.
    Det ændrer ikke automatisk videnspostens status.

    details må kun indeholde godkendte metadata og
    aggregater, ikke følsomme projekt- eller persondata.
    """

    __tablename__ = "knowledge_evidence"

    __table_args__ = (
        Index(
            "ix_knowledge_evidence_entry_checked",
            "entry_id",
            "checked_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    entry_id: Mapped[int] = mapped_column(
        ForeignKey(
            "knowledge_entries.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    verification_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    scope: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    outcome: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    checked_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    matched_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    unmatched_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    verified_by: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    entry: Mapped["KnowledgeEntry"] = relationship(
        back_populates="evidence"
    )
