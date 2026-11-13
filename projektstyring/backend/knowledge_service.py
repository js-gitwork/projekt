
"""
Rørbots selvstændige videnshukommelse.

FORMÅL
------
Rørbot kan uden manuel godkendelse:
- gemme nye opdagelser
- forbedre eksisterende viden
- genfinde tidligere opdagelser
- markere forældet eller forkert viden

Alle registreringer gemmes i PostgreSQL.

ANSVARSFORDELING
----------------
AI:
    Bestemmer, hvad der er værd at lære og revidere.

KnowledgeService:
    Validerer data, dokumenterer revisioner og beskytter
    katalogets integritet.

KnowledgeRepository:
    Udfører databaseoperationerne.

C5:
    Forbliver read-only. Denne service har ingen C5-adgang.

VERIFICERING
------------
Ny eller ændret viden får status "discovered".

Tekniske verificeringer implementeres separat gennem
kontrollerede værktøjer, som udfører undersøgelserne.

AI'ens egne udsagn kan aldrig alene udgøre bevis for,
at en teknisk verificering er gennemført.

TRANSAKTIONER
-------------
Den kaldende kode ejer SQLAlchemy-sessionen og skal
committe eller rulle tilbage som én samlet transaktion.

Ingen funktion i denne fil foretager commit.

SIKKERHED
---------
Denne service må kun få skriveadgang til videnskataloget
gennem betroet applikationskode.

Den giver ikke adgang til vilkårlig SQL eller til
ændringer i projektdata.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from projektstyring.backend.db_models.knowledge import (
    KnowledgeEntry,
    KnowledgeEvidence,
    KnowledgeSource,
)
from projektstyring.backend.repositories.knowledge_repository import (
    KnowledgeRepository,
)


ALLOWED_KNOWLEDGE_TYPES = frozenset({
    "relationship",
    "field_meaning",
    "investigation_method",
    "calculation_method",
    "business_concept",
    "observation",
})

MAX_DEFINITION_BYTES = 32768
MAX_DESCRIPTION_LENGTH = 8000


def _required_text(
    value: str,
    *,
    name: str,
    max_length: int,
) -> str:
    """Kontrollér et obligatorisk tekstfelt."""

    if not isinstance(value, str):
        raise ValueError(f"{name} skal være tekst.")

    result = value.strip()

    if not result:
        raise ValueError(f"{name} må ikke være tom.")

    if len(result) > max_length:
        raise ValueError(
            f"{name} må højst være {max_length} tegn."
        )

    return result


def _validate_definition(
    definition: dict[str, Any],
) -> dict[str, Any]:
    """
    Kontrollér at definitionen kan gemmes som JSONB.

    En definition behandles altid som data.
    Eventuelle SQL- eller kodefelter må aldrig udføres
    direkte af denne service.
    """

    if not isinstance(definition, dict):
        raise ValueError(
            "definition skal være et JSON-objekt."
        )

    if not definition:
        raise ValueError(
            "definition må ikke være tom."
        )

    # Verificeringsstatus tilhører servicelaget og må
    # aldrig gemmes som en selvrapporteret AI-påstand.
    reserved_keys = {
        "verification_status",
        "verified",
        "verified_date",
        "verified_at",
        "verified_by",
        "verification_date",
        "verification_result",
        "verification_evidence",
    }

    def check_reserved_keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in reserved_keys:
                    raise ValueError(
                        f"Reserveret verificeringsfelt: {key}"
                    )
                check_reserved_keys(child)
        elif isinstance(value, list):
            for child in value:
                check_reserved_keys(child)

    check_reserved_keys(definition)

    # En relationstype beskriver relationens karakter.
    # En gennemført verificering dokumenteres særskilt.
    relationship_type = definition.get("relationship_type")
    if relationship_type is not None and relationship_type not in {
        "observed_join",
        "declared_foreign_key",
    }:
        raise ValueError(
            "Ugyldig relationstype: " + str(relationship_type)
        )

    try:
        serialized = json.dumps(
            definition,
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "definition skal indeholde gyldige JSON-data."
        ) from exc

    if len(serialized.encode("utf-8")) > MAX_DEFINITION_BYTES:
        raise ValueError(
            "definition overskrider den tilladte størrelse."
        )

    return json.loads(serialized)


TRUSTED_FIELD_DICTIONARY_ACTOR = "tom_field_dictionary_import"


def _is_documented_field_dictionary(session, entry):
    """Genkend aktuelt dokumenteret feltmetadata via revisionshistorik."""

    if entry.knowledge_type != "field_meaning":
        return False

    definition = entry.definition
    if not isinstance(definition, dict):
        return False

    if definition.get("documentation_kind") != "field_dictionary":
        return False

    fingerprint = definition.get("documentation_sha256")
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or any(c not in "0123456789abcdefABCDEF" for c in fingerprint)
    ):
        return False

    if not isinstance(definition.get("documentation_source"), str):
        return False

    if not definition["documentation_source"].strip():
        return False

    latest_revision = session.scalar(
        select(KnowledgeEvidence)
        .where(
            KnowledgeEvidence.entry_id == entry.id,
            KnowledgeEvidence.verification_type == "knowledge_revision",
        )
        .order_by(KnowledgeEvidence.id.desc())
        .limit(1)
    )

    return (
        latest_revision is not None
        and latest_revision.verified_by == TRUSTED_FIELD_DICTIONARY_ACTOR
        and latest_revision.outcome in {"created", "revised"}
    )


class KnowledgeService:
    """
    Applikationsservice for Rørbots videnskartotek.

    Rørbot kan selv vedligeholde viden. Registrering og
    teknisk verificering er separate handlinger.
    """

    def __init__(self, session: Session):
        self.session = session
        self.repository = KnowledgeRepository(session)

    def register_source(
        self,
        *,
        source_key: str,
        source_type: str,
        display_name: str,
    ) -> KnowledgeSource:
        """
        Registrér en datakilde fra betroet applikationskode.

        Denne metode er beregnet til adapteropsætning,
        ikke som et frit AI-værktøj til oprettelse af
        vilkårlige databaseforbindelser.
        """

        source_key = _required_text(
            source_key,
            name="source_key",
            max_length=100,
        )
        source_type = _required_text(
            source_type,
            name="source_type",
            max_length=50,
        )
        display_name = _required_text(
            display_name,
            name="display_name",
            max_length=200,
        )

        existing = self.repository.get_source(source_key)

        if existing is not None:
            if existing.source_type != source_type:
                raise ValueError(
                    "Datakildens type stemmer ikke overens."
                )
            return existing

        return self.repository.create_source(
            source_key=source_key,
            source_type=source_type,
            display_name=display_name,
        )

    def remember(
        self,
        *,
        source_key: str,
        knowledge_key: str,
        knowledge_type: str,
        description: str,
        definition: dict[str, Any],
        actor: str,
        reason: str = "Ny opdagelse",
    ) -> KnowledgeEntry:
        """
        Opret eller revidér viden uden manuel godkendelse.

        Hvis samme viden gemmes uændret, sker intet.

        En ændret tidligere verificeret definition
        bliver igen "discovered", indtil en ny teknisk
        kontrol har undersøgt den nye version.

        Alle faktiske revisioner registreres i evidence
        som historikhændelser, IKKE som verificeringer.

        actor skal fastsættes af den kaldende
        applikation, ikke frit af AI-modellen.
        """

        source_key = _required_text(
            source_key,
            name="source_key",
            max_length=100,
        )
        knowledge_key = _required_text(
            knowledge_key,
            name="knowledge_key",
            max_length=255,
        )
        description = _required_text(
            description,
            name="description",
            max_length=MAX_DESCRIPTION_LENGTH,
        )
        actor = _required_text(
            actor,
            name="actor",
            max_length=100,
        )
        reason = _required_text(
            reason,
            name="reason",
            max_length=255,
        )

        if knowledge_type not in ALLOWED_KNOWLEDGE_TYPES:
            raise ValueError(
                f"Ukendt knowledge_type: {knowledge_type}"
            )

        definition = _validate_definition(definition)

        source = self.repository.get_source(source_key)

        if source is None:
            raise ValueError(
                f"Ukendt datakilde: {source_key}"
            )

        entry = self.repository.get_entry(
            source_id=source.id,
            knowledge_key=knowledge_key,
        )

        if entry is None:
            entry = self.repository.create_discovery(
                source_id=source.id,
                knowledge_key=knowledge_key,
                knowledge_type=knowledge_type,
                description=description,
                definition=definition,
            )
            entry.schema_fingerprint = source.schema_fingerprint

            self.repository.add_evidence(
                entry_id=entry.id,
                verification_type="knowledge_revision",
                scope=source_key,
                outcome="created",
                verified_by=actor,
                details={
                    "reason": reason,
                    "note": "Historikhændelse, ikke verificering",
                },
            )

            return entry

        unchanged = (
            entry.knowledge_type == knowledge_type
            and entry.description == description
            and entry.definition == definition
            and entry.verification_status != "deprecated"
            and entry.schema_fingerprint == source.schema_fingerprint
        )

        if unchanged:
            return entry

        if entry.verification_status in {
            "technically_verified",
            "business_verified",
        }:
            raise ValueError(
                "Verificeret viden må ikke ændres gennem "
                "den almindelige læringsfunktion."
            )

        if (
            actor != TRUSTED_FIELD_DICTIONARY_ACTOR
            and _is_documented_field_dictionary(self.session, entry)
        ):
            raise ValueError(
                "Dokumenteret feltmetadata må ikke overskrives "
                "af en almindelig læringsrevision."
            )

        previous = {
            "knowledge_type": entry.knowledge_type,
            "description": entry.description,
            "definition": entry.definition,
            "verification_status": entry.verification_status,
            "schema_fingerprint": entry.schema_fingerprint,
        }

        entry.knowledge_type = knowledge_type
        entry.description = description
        entry.definition = definition
        entry.schema_fingerprint = source.schema_fingerprint
        entry.verification_status = "discovered"

        self.repository.add_evidence(
            entry_id=entry.id,
            verification_type="knowledge_revision",
            scope=source_key,
            outcome="revised",
            verified_by=actor,
            details={
                "reason": reason,
                "previous": previous,
                "note": "Historikhændelse, ikke verificering",
            },
        )

        self.session.flush()
        return entry

    def recall(
        self,
        *,
        source_key: str,
        knowledge_type: str | None = None,
        include_deprecated: bool = False,
        limit: int = 100,
    ) -> list[KnowledgeEntry]:
        """
        Genfind viden fra en registreret datakilde.

        Resultaterne omfatter også hypoteser. Den
        kaldende agent skal derfor kunne se forskellen
        på discovered og verificeret viden.

        Hvis datakildens skemafingerprint er ændret,
        udelades poster med et ældre fingerprint.
        """

        source = self.repository.get_source(source_key)

        if source is None:
            return []

        entries = self.repository.list_entries(
            source_id=source.id,
            knowledge_type=knowledge_type,
            limit=limit,
        )

        return [
            entry
            for entry in entries
            if (
                include_deprecated
                or entry.verification_status != "deprecated"
            )
            and entry.schema_fingerprint == source.schema_fingerprint
        ]

    def deprecate(
        self,
        *,
        source_key: str,
        knowledge_key: str,
        actor: str,
        reason: str,
    ) -> KnowledgeEntry:
        """
        Forkast en registrering uden menneskelig godkendelse.

        Posten slettes ikke. Den bevares med historik,
        så tidligere undersøgelser kan efterprøves.
        """

        actor = _required_text(
            actor,
            name="actor",
            max_length=100,
        )
        reason = _required_text(
            reason,
            name="reason",
            max_length=255,
        )

        source = self.repository.get_source(source_key)

        if source is None:
            raise ValueError("Datakilden findes ikke.")

        entry = self.repository.get_entry(
            source_id=source.id,
            knowledge_key=knowledge_key,
        )

        if entry is None:
            raise ValueError(
                "Vidensregistreringen findes ikke."
            )

        if entry.verification_status == "deprecated":
            return entry

        if entry.verification_status in {
            "technically_verified",
            "business_verified",
        }:
            raise ValueError(
                "Verificeret viden må ikke forkastes gennem "
                "den almindelige læringsfunktion."
            )

        if _is_documented_field_dictionary(self.session, entry):
            raise ValueError(
                "Dokumenteret feltmetadata må ikke forkastes "
                "gennem den almindelige læringsfunktion."
            )

        previous_status = entry.verification_status
        entry.verification_status = "deprecated"

        self.repository.add_evidence(
            entry_id=entry.id,
            verification_type="knowledge_revision",
            scope=source_key,
            outcome="deprecated",
            verified_by=actor,
            details={
                "reason": reason,
                "previous_status": previous_status,
                "note": "Historikhændelse, ikke verificering",
            },
        )

        self.session.flush()
        return entry
