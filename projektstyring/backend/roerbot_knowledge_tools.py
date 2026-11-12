
"""
Native AI-værktøjer til Rørbots KnowledgeCatalog.

Denne adapter oversætter AI-værktøjskald til KnowledgeService.

Mistral ejer videnskatalogets indhold og kan oprette,
revidere og forkaste viden uden manuel godkendelse.

Sikkerhedsgrænser:
- Datakilden og aktøridentiteten fastsættes af applikationen.
- AI kan ikke vælge databaseforbindelse eller udføre SQL her.
- Katalogændringer holdes adskilt fra projekt- og C5-data.
- Nye eller reviderede oplysninger er hypoteser indtil
  en uafhængig kontrol har dokumenteret deres gyldighed.
- Hvert skrivekald afsluttes i en databasetransaktion.

Produktionsintegration må først ske efter særskilte tests.
"""

from __future__ import annotations

from typing import Any

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.knowledge_service import KnowledgeService


SOURCE_KEY = "c5"
SOURCE_TYPE = "sqlserver"
SOURCE_NAME = "C5"
ACTOR = "roerbot_native_pilot"


KNOWLEDGE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "recall_knowledge",
            "description": (
                "Find tidligere lærte oplysninger om C5. "
                "Brug dette før nye undersøgelser. "
                "Status discovered betyder hypotese, "
                "ikke dokumenteret sandhed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "knowledge_type": {
                        "type": "string",
                        "enum": [
                            "relationship",
                            "field_meaning",
                            "investigation_method",
                            "calculation_method",
                            "business_concept",
                            "observation",
                        ],
                    },
                    "include_deprecated": {
                        "type": "boolean"
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_knowledge",
            "description": (
                "Gem eller forbedr din viden om C5. "
                "Du bestemmer selv, hvornår det er nyttigt. "
                "Beskriv konkrete observationer og deres "
                "begrænsninger. Gem aldrig rå projektdata "
                "eller personoplysninger. En registrering "
                "er ikke i sig selv en teknisk verificering."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "knowledge_key": {
                        "type": "string",
                        "description": (
                            "Stabil nøgle for emnet. "
                            "Genbrug samme nøgle ved revision."
                        ),
                    },
                    "knowledge_type": {
                        "type": "string",
                        "enum": [
                            "relationship",
                            "field_meaning",
                            "investigation_method",
                            "calculation_method",
                            "business_concept",
                            "observation",
                        ],
                    },
                    "description": {"type": "string"},
                    "definition": {
                        "type": "object",
                        "description": (
                            "Struktureret beskrivelse af "
                            "relationen eller metoden. "
                            "Gem metadata, ikke C5-rækker."
                        ),
                        "additionalProperties": True,
                    },
                    "reason": {
                        "type": "string",
                        "description": "Hvorfor denne viden gemmes eller revideres.",
                    },
                },
                "required": [
                    "knowledge_key",
                    "knowledge_type",
                    "description",
                    "definition",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deprecate_knowledge",
            "description": (
                "Forkast tidligere viden, hvis en ny "
                "undersøgelse viser, at den er forkert "
                "eller ikke længere brugbar. Historik bevares."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "knowledge_key": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["knowledge_key", "reason"],
            },
        },
    },
]


KNOWLEDGE_TOOL_NAMES = {
    item["function"]["name"] for item in KNOWLEDGE_TOOLS
}


def initialize_knowledge_source() -> None:
    """
    Registrer den betroede C5-kilde.

    AI'en kan ikke selv oprette vilkårlige datakilder.
    Denne opsætning er idempotent ved normal sekventiel brug.
    """
    with SessionLocal() as session:
        service = KnowledgeService(session)
        service.register_source(
            source_key=SOURCE_KEY,
            source_type=SOURCE_TYPE,
            display_name=SOURCE_NAME,
        )
        session.commit()


def execute_knowledge_tool(
    name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """
    Udfør et enkelt tilladt hukommelsesværktøj.

    Værktøjsnavn og argumenter kommer fra AI'en.
    Datakilde og actor bestemmes af applikationen.

    Undtagelser får sessionen til at rulle tilbage.
    """
    if name not in KNOWLEDGE_TOOL_NAMES:
        raise ValueError(f"Ukendt hukommelsesværktøj: {name}")

    if not isinstance(args, dict):
        raise ValueError("Værktøjsargumenter skal være et objekt.")

    with SessionLocal() as session:
        service = KnowledgeService(session)

        if name == "recall_knowledge":
            from sqlalchemy import select
            from projektstyring.backend.db_models.knowledge import (
                KnowledgeEvidence,
            )

            def technical_evidence(entry):
                # Teknisk evidens følger den relation, der
                # faktisk blev kontrolleret, ikke blot
                # videnspostens seneste revisionsnummer.
                #
                # Historikken indeholder tidligere definition
                # ved hver revision. Dermed kan vi rekonstruere
                # relationen på kontroltidspunktet.
                def signature(definition):
                    if not isinstance(definition, dict):
                        return None

                    fields = (
                        "left_table",
                        "left_field",
                        "right_table",
                        "right_field",
                        "relationship_type",
                    )

                    values = tuple(
                        definition.get(field)
                        for field in fields
                    )

                    if not all(
                        isinstance(value, str) and value
                        for value in values
                    ):
                        return None

                    return values

                current_signature = signature(entry.definition)

                if current_signature is None:
                    return []

                revisions = session.scalars(
                    select(KnowledgeEvidence)
                    .where(
                        KnowledgeEvidence.entry_id == entry.id,
                        KnowledgeEvidence.verification_type == "knowledge_revision",
                    )
                    .order_by(KnowledgeEvidence.id.asc())
                ).all()

                records = session.scalars(
                    select(KnowledgeEvidence)
                    .where(
                        KnowledgeEvidence.entry_id == entry.id,
                        KnowledgeEvidence.verification_type == "join_check",
                        KnowledgeEvidence.verified_by == "python:verify_join",
                    )
                    .order_by(KnowledgeEvidence.id.desc())
                ).all()

                result = []

                for item in records:
                    # Den første efterfølgende revision viser
                    # definitionen umiddelbart før ændringen.
                    next_revision = next(
                        (
                            revision for revision in revisions
                            if revision.id > item.id
                        ),
                        None,
                    )

                    if next_revision is None:
                        checked_definition = entry.definition
                    else:
                        previous = (
                            (next_revision.details or {})
                            .get("previous") or {}
                        )
                        checked_definition = previous.get("definition")

                    if signature(checked_definition) != current_signature:
                        continue

                    # Sammenhold også de tabeller, Python
                    # registrerede ved selve kontrollen.
                    details = item.details or {}

                    if (
                        details.get("left_table")
                        != current_signature[0]
                        or details.get("right_table")
                        != current_signature[2]
                    ):
                        continue

                    result.append({
                        "evidence_id": item.id,
                        "scope": item.scope,
                        "outcome": item.outcome,
                        "checked_count": item.checked_count,
                        "matched_count": item.matched_count,
                        "unmatched_count": item.unmatched_count,
                        "verified_by": item.verified_by,
                        "checked_at": item.checked_at.isoformat(),
                        "details": item.details,
                    })

                    if len(result) == 3:
                        break

                return result

            entries = service.recall(
                source_key=SOURCE_KEY,
                knowledge_type=args.get("knowledge_type"),
                include_deprecated=args.get(
                    "include_deprecated", False
                ),
                limit=100,
            )

            return {
                "entries": [
                    {
                        "knowledge_key": entry.knowledge_key,
                        "knowledge_type": entry.knowledge_type,
                        "description": entry.description,
                        "definition": entry.definition,
                        "verification_status": entry.verification_status,
                        "technical_evidence": technical_evidence(entry),
                        "claim_class": (
                            "unverified_field_interpretation"
                            if entry.knowledge_type == "field_meaning"
                            and entry.verification_status == "discovered"
                            else "unverified_observation"
                            if entry.knowledge_type == "observation"
                            and entry.verification_status == "discovered"
                            else "unverified_claim"
                            if entry.verification_status == "discovered"
                            else entry.verification_status
                        ),
                    }
                    for entry in entries
                ],
                "returned_count": len(entries),
                "note": (
                    "Discovered er en hypotese. "
                    "Brug C5-læseværktøjer til at kontrollere "
                    "viden, før du drager konklusioner."
                ),
            }

        if name == "remember_knowledge":
            entry = service.remember(
                source_key=SOURCE_KEY,
                knowledge_key=args["knowledge_key"],
                knowledge_type=args["knowledge_type"],
                description=args["description"],
                definition=args["definition"],
                reason=args.get(
                    "reason", "Opdagelse fra C5-undersøgelse"
                ),
                actor=ACTOR,
            )
            result = {
                "knowledge_key": entry.knowledge_key,
                "verification_status": entry.verification_status,
                "saved": True,
            }
            session.commit()
            return result

        entry = service.deprecate(
            source_key=SOURCE_KEY,
            knowledge_key=args["knowledge_key"],
            reason=args["reason"],
            actor=ACTOR,
        )
        result = {
            "knowledge_key": entry.knowledge_key,
            "verification_status": entry.verification_status,
            "saved": True,
        }
        session.commit()
        return result
