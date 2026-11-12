
"""
Dokumenteret relationskontrol for Rørbots KnowledgeCatalog.

FORMÅL
------
Kontrollerer en tidligere opdaget databaserelation med
faktisk indlæste data og gemmer resultatet som evidens.

SIKKERHED OG DATAKVALITET
-------------------------
- Accepterer kun komplette datasæt.
- Kontrollerer at relationen svarer til vidensposten.
- Bruger den deterministiske Python-verifikator.
- Gemmer aggregater, aldrig komplette C5-rækker.
- Ændrer ikke KnowledgeEntry.verification_status.
- Skriver ikke til C5 eller projektdata.
- Foretager ikke commit; den kaldende kode ejer transaktionen.

Et bestået resultat gælder kun det dokumenterede omfang.
Det er ikke et bevis for en deklareret foreign key eller
forretningsmæssig korrekthed.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from projektstyring.backend.knowledge_verification import verify_join
from projektstyring.backend.repositories.knowledge_repository import (
    KnowledgeRepository,
)


def require_complete_dataset(
    *,
    rows: list[dict[str, Any]],
    total_rows: int,
) -> None:
    """
    Afvis ufuldstændige eller inkonsistente datasæt.

    total_rows skal komme fra en betroet dataadapter,
    ikke fra AI-modellens egen angivelse.

    Kontrollen forudsætter, at dataadapteren har samlet
    unikke rækker med stabile identifikatorer.
    """

    if (
        isinstance(total_rows, bool)
        or not isinstance(total_rows, int)
        or total_rows < 0
    ):
        raise ValueError("Ugyldigt total_rows.")

    if len(rows) != total_rows:
        raise ValueError(
            f"Ufuldstændigt datasæt: "
            f"{len(rows)} af {total_rows} rækker."
        )


def verify_and_record_join(
    *,
    session: Session,
    source_key: str,
    knowledge_key: str,
    project_id: str,
    left_table: str,
    right_table: str,
    left_key: str,
    right_key: str,
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    left_total_rows: int,
    right_total_rows: int,
) -> dict[str, Any]:
    """
    Kontrollér en katalogrelation og gem ét måleresultat.

    relationens kilde, tabeller og felter kontrolleres mod
    den eksisterende videnspost, før der gemmes evidens.

    Funktionen må ikke modtage kunstigt reducerede datasæt
    med en tilsvarende reduceret total_rows-værdi.
    Den kaldende adapter skal levere pålidelige totaler.

    Kun betroet applikationskode må kalde denne funktion.
    """

    require_complete_dataset(
        rows=left_rows,
        total_rows=left_total_rows,
    )
    require_complete_dataset(
        rows=right_rows,
        total_rows=right_total_rows,
    )

    if not project_id or len(project_id) > 150:
        raise ValueError("Ugyldig projektidentifikator.")

    repository = KnowledgeRepository(session)
    source = repository.get_source(source_key)

    if source is None:
        raise ValueError("Datakilden findes ikke.")

    entry = repository.get_entry(
        source_id=source.id,
        knowledge_key=knowledge_key,
    )

    if entry is None:
        raise ValueError("Vidensregistreringen findes ikke.")

    if entry.knowledge_type != "relationship":
        raise ValueError("Vidensposten beskriver ikke en relation.")

    if entry.verification_status == "deprecated":
        raise ValueError("Forældet relation må ikke verificeres.")

    if entry.schema_fingerprint != source.schema_fingerprint:
        raise ValueError("Datakildens skema har ændret sig.")

    definition = entry.definition

    expected = {
        "left_table": left_table,
        "right_table": right_table,
        "left_field": left_key,
        "right_field": right_key,
    }

    for field, value in expected.items():
        if definition.get(field) != value:
            raise ValueError(
                f"Relationen stemmer ikke med kataloget: {field}"
            )

    if definition.get("relationship_type") != "observed_join":
        raise ValueError(
            "Kun observerede sammenkoblinger understøttes."
        )

    result = verify_join(
        left_rows=left_rows,
        right_rows=right_rows,
        left_key=left_key,
        right_key=right_key,
    )

    evidence = repository.add_evidence(
        entry_id=entry.id,
        verification_type="join_check",
        scope=f"project:{project_id}",
        outcome=result["outcome"],
        verified_by="python:verify_join",
        checked_count=result["checked_count"],
        matched_count=result["matched_count"],
        unmatched_count=result["unmatched_count"],
        details={
            "source_key": source_key,
            "left_table": left_table,
            "right_table": right_table,
            "left_total_rows": left_total_rows,
            "right_total_rows": right_total_rows,
            "left_null_keys": result["left_null_keys"],
            "right_null_keys": result["right_null_keys"],
            "duplicate_right_keys": result["duplicate_right_keys"],
            "rows_with_multiple_matches": result[
                "rows_with_multiple_matches"
            ],
            "match_rate": result["match_rate"],
            "complete_datasets": True,
            "scope_type": "single_project",
        },
    )

    session.flush()

    return {
        "evidence_id": evidence.id,
        "knowledge_key": entry.knowledge_key,
        "outcome": result["outcome"],
        "checked_count": result["checked_count"],
        "matched_count": result["matched_count"],
        "unmatched_count": result["unmatched_count"],
        "duplicate_right_keys": result["duplicate_right_keys"],
        "scope": f"project:{project_id}",
        "verification_status": entry.verification_status,
        "note": (
            "Kontrollen dokumenterer et teknisk resultat "
            "for dette projekt. Den ændrer ikke automatisk "
            "videnspostens generelle verificeringsstatus."
        ),
    }
