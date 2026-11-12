
"""
Rørbots værktøj til teknisk verificering af relationer.

AI vælger en eksisterende videnspost.
Python finder tabeller og felter i KnowledgeCatalog,
læser komplette projektdata fra C5 og beregner evidens.

C5 anvendes udelukkende read-only.
Ingen projektdata ændres.

En bestået kontrol dokumenterer en observeret relation
på ét projekt. Den beviser ikke, at relationen er en
deklareret foreign key eller en generel forretningsregel.
"""

from __future__ import annotations

from typing import Any

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.repositories.knowledge_repository import (
    KnowledgeRepository,
)
from projektstyring.backend.roerbot_data_agent import (
    ALLOWED_TABLES,
    get_schema,
    read_c5,
)
from projektstyring.backend.knowledge_evidence_service import (
    verify_and_record_join,
)

PAGE_SIZE = 100
MAX_DATASET_ROWS = 10000


RELATIONSHIP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "verify_knowledge_relationship",
            "description": (
                "Efterprøv en tidligere opdaget C5-relation "
                "med komplette projektdata. Python henter "
                "selv tabeller og felter fra KnowledgeCatalog, "
                "beregner match og gemmer teknisk evidens. "
                "Kontrollen gælder kun det angivne projekt."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "knowledge_key": {
                        "type": "string",
                        "description": (
                            "Nøglen på den eksisterende "
                            "relationspost i KnowledgeCatalog."
                        ),
                    },
                },
                "required": ["knowledge_key"],
                "additionalProperties": False,
            },
        },
    },
]


def _read_complete_project_table(
    *,
    table: str,
    project_id: str,
    required_column: str,
) -> tuple[list[dict[str, Any]], int]:
    """
    Hent samtlige projektposter gennem C5-adapteren.

    Adapterens total_rows bestemmer omfanget.
    AI kan ikke selv begrænse antal rækker.

    ROWNUMBER bruges til at opdage dubletter mellem
    sider, så gentagne sider ikke fremstår komplette.
    """

    available = {
        item["COLUMN_NAME"]
        for item in get_schema(table)
    }

    if required_column not in available:
        raise ValueError(
            f"{table} mangler feltet {required_column}."
        )

    if "ROWNUMBER" not in available:
        raise ValueError(
            f"{table} mangler stabil rækkeidentifikator."
        )

    columns = list(dict.fromkeys([
        "ROWNUMBER",
        required_column,
    ]))

    rows: list[dict[str, Any]] = []
    seen_ids: set[Any] = set()
    offset = 0
    expected_total = None

    while True:
        result = read_c5(
            table=table,
            project_id=project_id,
            columns=columns,
            limit=PAGE_SIZE,
            offset=offset,
        )

        total = result["total_rows"]

        if (
            isinstance(total, bool)
            or not isinstance(total, int)
            or total < 0
        ):
            raise ValueError("C5 returnerede ugyldigt rækkeantal.")

        if total > MAX_DATASET_ROWS:
            raise ValueError(
                f"{table} har {total} rækker. "
                "Den sikre læsegrænse er overskredet."
            )

        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise ValueError(
                f"{table} ændrede rækkeantal under læsningen."
            )

        page = result["rows"]

        if not isinstance(page, list):
            raise ValueError("C5 returnerede ugyldige rækker.")

        if len(page) > PAGE_SIZE:
            raise ValueError("C5 returnerede for mange rækker.")

        for row in page:
            if not isinstance(row, dict):
                raise ValueError("Ugyldig C5-række.")

            if required_column not in row:
                raise ValueError(
                    f"Rækken mangler {required_column}."
                )

            row_id = row.get("ROWNUMBER")

            if row_id is None:
                raise ValueError("Rækken mangler ROWNUMBER.")

            if row_id in seen_ids:
                raise ValueError(
                    f"Dubleret C5-rækkeidentifikator i {table}."
                )

            seen_ids.add(row_id)
            rows.append(row)

        offset += len(page)

        if not result["has_more"]:
            break

        if not page:
            raise ValueError(
                "C5 angiver flere sider, men returnerer ingen rækker."
            )

        if offset >= expected_total:
            raise ValueError(
                "C5 angiver flere sider end forventet."
            )

    if len(rows) != expected_total:
        raise ValueError(
            f"Ufuldstændigt datasæt i {table}: "
            f"{len(rows)} af {expected_total}."
        )

    return rows, expected_total


def verify_relationship(
    *,
    knowledge_key: str,
    project_id: str,
) -> dict[str, Any]:
    """
    Verificér en observeret relation på ét C5-projekt.

    Kun knowledge_key vælges af AI.
    Projektidentifikatoren kommer fra pilotens kontekst.

    Evidens gemmes først, når begge fulde datasæt
    er læst, og Python har udført kontrollen.
    """

    if not isinstance(knowledge_key, str) or not knowledge_key.strip():
        raise ValueError("knowledge_key mangler.")

    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("project_id mangler.")

    with SessionLocal() as session:
        repository = KnowledgeRepository(session)

        source = repository.get_source("c5")

        if source is None:
            raise ValueError("C5-kilden findes ikke.")

        entry = repository.get_entry(
            source_id=source.id,
            knowledge_key=knowledge_key,
        )

        if entry is None:
            raise ValueError("Vidensposten findes ikke.")

        if entry.knowledge_type != "relationship":
            raise ValueError("Vidensposten er ikke en relation.")

        if entry.verification_status == "deprecated":
            raise ValueError("Relationen er forældet.")

        if entry.schema_fingerprint != source.schema_fingerprint:
            raise ValueError("C5-skemaet har ændret sig.")

        definition = entry.definition

        if definition.get("relationship_type") != "observed_join":
            raise ValueError(
                "Kun observerede relationer understøttes."
            )

        left_table = definition["left_table"].upper()
        right_table = definition["right_table"].upper()
        left_key = definition["left_field"].upper()
        right_key = definition["right_field"].upper()

        allowed = {table.upper() for table in ALLOWED_TABLES}

        if left_table not in allowed or right_table not in allowed:
            raise ValueError(
                "Relationen omfatter en ikke-tilladt tabel."
            )

        left_rows, left_total = _read_complete_project_table(
            table=left_table,
            project_id=project_id,
            required_column=left_key,
        )

        right_rows, right_total = _read_complete_project_table(
            table=right_table,
            project_id=project_id,
            required_column=right_key,
        )

        result = verify_and_record_join(
            session=session,
            source_key="c5",
            knowledge_key=knowledge_key,
            project_id=project_id,
            left_table=left_table,
            right_table=right_table,
            left_key=left_key,
            right_key=right_key,
            left_rows=left_rows,
            right_rows=right_rows,
            left_total_rows=left_total,
            right_total_rows=right_total,
        )

        session.commit()

        return result
