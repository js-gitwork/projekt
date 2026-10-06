from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from projektstyring.backend.project_creation_parser import (
    parse_project_creation_request,
)
from projektstyring.backend.project_factory import (
    create_project,
)
from projektstyring.backend.installation_service import (
    create_installations,
)
from projektstyring.backend.project_repository import (
    ProjectRepository,
)
from projektstyring.backend.repositories.conversation_state_repository import (
    clear_active_conversation,
    get_active_conversation,
    save_active_conversation,
)


PROJECT_CREATION_WORKFLOW = "project_creation"


@dataclass(frozen=True)
class ProjectCreationField:
    name: str
    prompt: str
    reason: str = ""


PROJECT_CREATION_FIELDS = (
    ProjectCreationField(
        name="project_id",
        prompt="Hvad er projektets V-nummer?",
    ),
    ProjectCreationField(
        name="name",
        prompt="Hvad skal projektet hedde?",
    ),
    ProjectCreationField(
        name="customer",
        prompt="Hvem er kunden?",
    ),
)


FIELD_LABELS = {
    "project_id": "V-nummer",
    "name": "Projektnavn",
    "customer": "Kunde",
    "city": "By/område",
    "start_date": "Startdato",
    "project_manager": "Projektleder",
    "site_manager": "Entrepriseleder",
    "installation_count": "Antal installationer",
}

project_repository = ProjectRepository()


def clean_data(
    data: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        key: value
        for key, value in (
            data or {}
        ).items()
        if value not in {
            None,
            "",
        }
    }


def merge_data(
    existing_data: dict[str, Any] | None,
    new_data: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(
        existing_data or {}
    )

    for key, value in (
        new_data or {}
    ).items():
        if value not in {
            None,
            "",
        }:
            merged[key] = value

    return merged


def analyze_project_creation(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Kontrollerer obligatoriske projektoplysninger og
    medtager samtidig alle kendte valgfrie oplysninger
    i projektoversigten.
    """

    missing = []

    # Alle kendte oplysninger skal vises, også valgfrie.
    provided = {
        field: value
        for field, value in data.items()
        if value is not None
        and value != ""
        and field in FIELD_LABELS
    }

    # Kun felterne i PROJECT_CREATION_FIELDS
    # er obligatoriske.
    for field in PROJECT_CREATION_FIELDS:
        value = data.get(field.name)

        if value is not None and value != "":
            continue

        missing.append(
            {
                "field": field.name,
                "label": FIELD_LABELS.get(
                    field.name,
                    field.name,
                ),
                "prompt": field.prompt,
                "reason": field.reason,
            }
        )

    return {
        "workflow": PROJECT_CREATION_WORKFLOW,
        "complete": not missing,
        "provided": provided,
        "missing": missing,
        "next_question": (
            missing[0]["prompt"]
            if missing
            else None
        ),
    }


def normalize_project_creation_fields(
    fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Validerer feltværdier fra den eksisterende AI-interpreter.

    AI'en fortolker betydningen. Python kontrollerer,
    hvilke værdier der må gemmes i projektudkastet.
    """
    allowed_text_fields = {
        "name",
        "customer",
        "project_manager",
        "site_manager",
        "city",
        "preparation_team",
    }

    result = {}

    for key, value in (fields or {}).items():
        if value is None or isinstance(value, (bool, dict, list)):
            continue

        if key == "project_id":
            candidate = str(value).strip().upper()

            if (
                candidate.startswith("V")
                and len(candidate) > 1
                and candidate[1:].isdigit()
            ):
                result[key] = candidate

        elif key == "installation_count":
            try:
                count = int(value)
            except (TypeError, ValueError):
                continue

            if count > 0:
                result[key] = count

        elif key == "start_date":
            try:
                result[key] = date.fromisoformat(
                    str(value).strip()
                ).isoformat()
            except (TypeError, ValueError):
                continue

        elif key in allowed_text_fields:
            candidate = str(value).strip()

            if candidate:
                result[key] = candidate

    return result


def build_project_from_creation_data(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Bygger projektet ud fra det godkendte projektudkast.

    Installationerne oprettes uden surveyresultater.
    Survey forbliver i sin oprindelige, uafsluttede tilstand.
    """

    project = create_project(
        project_id=data["project_id"],
        name=data["name"],
        customer=data.get("customer", ""),
        project_manager=data.get(
            "project_manager",
            "",
        ),
        site_manager=data.get(
            "site_manager",
            "",
        ),
        city=data.get("city", ""),
        start_date=data.get("start_date", ""),
        notes=(
            "Oprettet som udkast via Rørbot."
        ),
    )

    installation_count = int(
        data.get("installation_count") or 0
    )

    create_installations(
        project,
        installation_count,
    )

    return project


def handle_project_creation_message(
    text: str,
    *,
    interpretation: dict[str, Any],
    user_key: str,
    conversation_key: str,
) -> dict[str, Any]:
    """
    Behandler interpreterens strukturerede projektbeslutning.

    Funktionen foretager ingen selvstændig AI-fortolkning.
    Projektet gemmes kun ved en særskilt godkendelse.
    """

    action = interpretation.get(
        "project_creation_action"
    )

    fields = normalize_project_creation_fields(
        interpretation.get("project_creation_fields")
    )

    active_state = get_active_conversation(
        user_key=user_key,
        conversation_key=conversation_key,
    )

    has_active_draft = (
        active_state is not None
        and active_state.workflow == PROJECT_CREATION_WORKFLOW
    )

    existing_data = (
        dict(active_state.data or {})
        if has_active_draft
        else {}
    )

    existing_analysis = analyze_project_creation(
        existing_data
    )

    # Godkendelse må aldrig indeholde samtidige rettelser.
    if action == "approve":
        if fields:
            return {
                "analysis": existing_analysis,
                "data": existing_data,
                "answer": (
                    "Jeg har registreret nye oplysninger "
                    "sammen med godkendelsen. "
                    "Projektet er ikke oprettet. "
                    "Send rettelsen først, så viser jeg "
                    "det opdaterede udkast til godkendelse."
                ),
            }

        if not has_active_draft:
            return {
                "analysis": existing_analysis,
                "data": existing_data,
                "answer": (
                    "Der findes ikke et aktivt "
                    "projektudkast at godkende."
                ),
            }

        if not existing_analysis["complete"]:
            return {
                "analysis": existing_analysis,
                "data": existing_data,
                "answer": format_project_creation_analysis(
                    existing_analysis
                ),
            }

        project = build_project_from_creation_data(
            existing_data
        )

        saved_project = project_repository.save_project(
            project
        )

        clear_active_conversation(
            user_key=user_key,
            conversation_key=conversation_key,
        )

        return {
            "analysis": existing_analysis,
            "data": existing_data,
            "project": saved_project,
            "answer": (
                f"Projekt {project['id']} — "
                f"{project['name']} er oprettet "
                "som udkast."
            ),
        }

    # Annullering rydder projektoprettelsen i den aktuelle
    # samtale. Selve Rørbot-fanen bevares.
    if action == "cancel":
        if has_active_draft:
            clear_active_conversation(
                user_key=user_key,
                conversation_key=conversation_key,
            )

        return {
            "analysis": existing_analysis,
            "data": {},
            "answer": (
                "Projektoprettelsen er annulleret. "
                "Der er ikke oprettet noget projekt."
            ),
        }

    if action == "unrelated":
        return {
            "analysis": existing_analysis,
            "data": existing_data,
            "answer": (
                "Beskeden vedrører ikke projektoprettelsen. "
                "Projektudkastet er uændret."
            ),
        }

    if action == "question":
        if not has_active_draft:
            return {
                "analysis": existing_analysis,
                "data": existing_data,
                "answer": (
                    "Der er ikke nogen aktiv "
                    "projektoprettelse."
                ),
            }

        return {
            "analysis": existing_analysis,
            "data": existing_data,
            "answer": format_project_creation_analysis(
                existing_analysis
            ),
        }

    if action != "update" or not fields:
        return {
            "analysis": existing_analysis,
            "data": existing_data,
            "answer": (
                "Jeg kunne ikke udlede en sikker "
                "projektændring. Udkastet er uændret."
            ),
        }

    merged_data = merge_data(
        existing_data,
        fields,
    )

    analysis = analyze_project_creation(
        merged_data
    )

    save_active_conversation(
        workflow=PROJECT_CREATION_WORKFLOW,
        data=merged_data,
        user_key=user_key,
        conversation_key=conversation_key,
    )

    return {
        "analysis": analysis,
        "data": merged_data,
        "answer": format_project_creation_analysis(
            analysis,
            updated_fields=list(fields.keys()),
        ),
    }

def format_project_creation_analysis(
    analysis: dict[str, Any],
    updated_fields: list[str] | None = None,
) -> str:
    updated_fields = (
        updated_fields
        or []
    )

    lines = [
        "Jeg kan hjælpe med at oprette projektet.",
        "",
    ]

    if updated_fields:
        lines.append(
            "Jeg har opdateret:"
        )

        for field in updated_fields:
            label = FIELD_LABELS.get(
                field,
                field,
            )

            value = (
                analysis[
                    "provided"
                ].get(field)
            )

            lines.append(
                f"• {label}: {value}"
            )

        lines.append("")

    if analysis["provided"]:
        lines.append(
            "Jeg har disse oplysninger:"
        )

        for field, value in (
            analysis[
                "provided"
            ].items()
        ):
            label = FIELD_LABELS.get(
                field,
                field,
            )

            lines.append(
                f"• {label}: {value}"
            )

    if analysis["missing"]:
        lines.append("")
        lines.append(
            "Jeg mangler:"
        )

        for item in (
            analysis[
                "missing"
            ]
        ):
            line = (
                f"• {item['label']}"
            )

            if item.get(
                "reason"
            ):
                line += (
                    f" — {item['reason']}"
                )

            lines.append(
                line
            )

        lines.append("")
        lines.append(
            analysis[
                "next_question"
            ]
        )

    else:
        lines.append("")
        lines.append(
            "Alle nødvendige oplysninger "
            "er til stede."
        )
        lines.append(
            "Skal jeg oprette projektet "
            "som udkast?"
        )

    return "\n".join(
        lines
    )
