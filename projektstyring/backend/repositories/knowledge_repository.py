
"""
Databaseadgang til Rørbots KnowledgeCatalog.

FORMÅL
------
Læser og gemmer datakilder, vidensregistreringer og
dokumentation for undersøgelser.

ARKITEKTUR
----------
Repository-laget ejer PostgreSQL-adgangen.

AI-agenten må ikke kalde dette repository direkte.
Det skal ske gennem KnowledgeService, som kontrollerer
rettigheder og verificeringsregler.

Repository foretager aldrig selv en vurdering af,
om en AI-opdagelse er korrekt.

TRANSAKTIONER
-------------
Repository modtager en SQLAlchemy Session fra den
kaldende service. Den kalder hverken commit eller
rollback.

Dermed kan ændringer og verificeringsregistreringer
gemmes atomisk af servicelaget.

VEDLIGEHOLDELSE
---------------
Modeller:
    db_models/knowledge.py

Database:
    knowledge_sources
    knowledge_entries
    knowledge_evidence

Migration:
    436c3d33ff73
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from projektstyring.backend.db_models.knowledge import (
    KnowledgeSource,
    KnowledgeEntry,
    KnowledgeEvidence,
)


class KnowledgeRepository:
    """Persistence for det modeluafhængige videnskatalog."""

    def __init__(self, session: Session):
        self.session = session

    # ---------------------------------------------------------
    # Datakilder
    # ---------------------------------------------------------

    def get_source(
        self,
        source_key: str,
    ) -> KnowledgeSource | None:
        """Find en datakilde ud fra dens stabile nøgle."""

        statement = select(KnowledgeSource).where(
            KnowledgeSource.source_key == source_key
        )

        return self.session.scalar(statement)

    def create_source(
        self,
        *,
        source_key: str,
        source_type: str,
        display_name: str,
    ) -> KnowledgeSource:
        """
        Registrér en ny datakilde.

        Opretter ikke forbindelse til datakilden.
        Det ansvar tilhører den relevante adapter.
        """

        if self.get_source(source_key) is not None:
            raise ValueError(
                f"Datakilden findes allerede: {source_key}"
            )

        source = KnowledgeSource(
            source_key=source_key,
            source_type=source_type,
            display_name=display_name,
        )

        self.session.add(source)
        self.session.flush()

        return source

    # ---------------------------------------------------------
    # Vidensregistreringer
    # ---------------------------------------------------------

    def get_entry(
        self,
        *,
        source_id: int,
        knowledge_key: str,
    ) -> KnowledgeEntry | None:
        """Find én konkret vidensregistrering."""

        statement = select(KnowledgeEntry).where(
            KnowledgeEntry.source_id == source_id,
            KnowledgeEntry.knowledge_key == knowledge_key,
        )

        return self.session.scalar(statement)

    def list_entries(
        self,
        *,
        source_id: int,
        knowledge_type: str | None = None,
        verification_status: str | None = None,
        limit: int = 100,
    ) -> list[KnowledgeEntry]:
        """
        Find tidligere registreret viden.

        Begrænser antallet af resultater, så en AI-agent
        ikke utilsigtet indlæser hele kataloget.
        """

        if not 1 <= limit <= 100:
            raise ValueError(
                "Limit skal være mellem 1 og 100."
            )

        statement = select(KnowledgeEntry).where(
            KnowledgeEntry.source_id == source_id
        )

        if knowledge_type is not None:
            statement = statement.where(
                KnowledgeEntry.knowledge_type
                == knowledge_type
            )

        if verification_status is not None:
            statement = statement.where(
                KnowledgeEntry.verification_status
                == verification_status
            )

        statement = statement.order_by(
            KnowledgeEntry.knowledge_key
        ).limit(limit)

        return list(self.session.scalars(statement))

    def create_discovery(
        self,
        *,
        source_id: int,
        knowledge_key: str,
        knowledge_type: str,
        description: str,
        definition: dict[str, Any],
    ) -> KnowledgeEntry:
        """
        Gem en endnu ikke verificeret opdagelse.

        Status er ALTID discovered.

        Verificeringsstatus må ikke angives af AI'en
        eller af dette repositories kaldende klient.
        """

        if self.get_entry(
            source_id=source_id,
            knowledge_key=knowledge_key,
        ) is not None:
            raise ValueError(
                "Vidensregistreringen findes allerede."
            )

        entry = KnowledgeEntry(
            source_id=source_id,
            knowledge_key=knowledge_key,
            knowledge_type=knowledge_type,
            description=description,
            definition=definition,
            verification_status="discovered",
        )

        self.session.add(entry)
        self.session.flush()

        return entry

    # ---------------------------------------------------------
    # Dokumentation for undersøgelser
    # ---------------------------------------------------------

    def add_evidence(
        self,
        *,
        entry_id: int,
        verification_type: str,
        scope: str,
        outcome: str,
        verified_by: str,
        checked_count: int | None = None,
        matched_count: int | None = None,
        unmatched_count: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> KnowledgeEvidence:
        """
        Registrér resultatet af en undersøgelse.

        Evidence ændrer ikke automatisk entry-status.

        Servicelaget skal afgøre, om undersøgelsen
        opfylder betingelserne for verificering.
        """

        entry = self.session.get(
            KnowledgeEntry,
            entry_id,
        )

        if entry is None:
            raise ValueError(
                "Vidensregistreringen findes ikke."
            )

        evidence = KnowledgeEvidence(
            entry_id=entry_id,
            verification_type=verification_type,
            scope=scope,
            outcome=outcome,
            verified_by=verified_by,
            checked_count=checked_count,
            matched_count=matched_count,
            unmatched_count=unmatched_count,
            details=details or {},
        )

        self.session.add(evidence)
        self.session.flush()

        return evidence

    def list_evidence(
        self,
        *,
        entry_id: int,
        limit: int = 100,
    ) -> list[KnowledgeEvidence]:
        """Hent undersøgelseshistorikken for én registrering."""

        if not 1 <= limit <= 100:
            raise ValueError(
                "Limit skal være mellem 1 og 100."
            )

        statement = (
            select(KnowledgeEvidence)
            .where(
                KnowledgeEvidence.entry_id == entry_id
            )
            .order_by(
                KnowledgeEvidence.checked_at.desc(),
                KnowledgeEvidence.id.desc(),
            )
            .limit(limit)
        )

        return list(self.session.scalars(statement))
