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
    ProjectCreationField(
        name="city",
        prompt=(
            "Hvilken by eller hvilket område "
            "ligger projektet i?"
        ),
    ),
    ProjectCreationField(
        name="start_date",
        prompt="Hvornår starter projektet?",
    ),
    ProjectCreationField(
        name="installation_count",
        prompt="Hvor mange installationer er der?",
    ),
)


FIELD_LABELS = {
    "project_id": "V-nummer",
    "name": "Projektnavn",
    "customer": "Kunde",
    "city": "By/område",
    "start_date": "Startdato",
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
    missing = []
    provided = {}

    for field in PROJECT_CREATION_FIELDS:
        value = data.get(
            field.name
        )

        if value not in {
            None,
            "",
        }:
            provided[field.name] = value
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
        "workflow": (
            PROJECT_CREATION_WORKFLOW
        ),
        "complete": not missing,
        "provided": provided,
        "missing": missing,
        "next_question": (
            missing[0]["prompt"]
            if missing
            else None
        ),
    }


def parse_followup_answer(
    text: str,
    active_data: dict[str, Any],
    *,
    default_year: int,
) -> dict[str, Any]:
    parsed = (
        parse_project_creation_request(
            text,
            default_year=default_year,
        )
    )

    cleaned = clean_data(
        parsed
    )

    if cleaned:
        return cleaned

    analysis = (
        analyze_project_creation(
            active_data
        )
    )

    missing = (
        analysis.get("missing")
        or []
    )

    if not missing:
        return {}

    next_field = str(
        missing[0]["field"]
    )

    value = str(
        text or ""
    ).strip()

    if not value:
        return {}

    return {
        next_field: value,
    }


def is_confirmation(
    text: str,
) -> bool:
    normalized = str(
        text or ""
    ).strip().casefold()

    return normalized in {
        "ja",
        "ja tak",
        "opret",
        "opret projektet",
        "gem",
        "gem projektet",
    }


def build_project_from_creation_data(
    data: dict[str, Any],
) -> dict[str, Any]:
    project = create_project(
        project_id=data.get(
            "project_id"
        ),
        name=data.get(
            "name"
        ),
        customer=data.get(
            "customer",
            "",
        ),
        city=data.get(
            "city",
            "",
        ),
        start_date=data.get(
            "start_date",
            "",
        ),
        notes=(
            "Oprettet som udkast via Rørbot."
        ),
    )

    project["installations"] = []

    return project


def handle_project_creation_message(
    text: str,
    *,
    default_year: int | None = None,
    user_key: str = "default",
) -> dict[str, Any]:
    """
    Behandler en projektoprettelsesdialog.

    Conversation state bruges kun til den midlertidige dialog.
    Det færdige projekt gemmes gennem ProjectRepository.

    Servicen håndterer ingen andre workflows eller beslutninger.
    """

    resolved_year = (
        default_year
        if default_year is not None
        else date.today().year
    )

    normalized_text = str(
        text or ""
    ).strip()

    active_state = (
        get_active_conversation(
            user_key
        )
    )

    if (
        active_state is not None
        and active_state.workflow
        == PROJECT_CREATION_WORKFLOW
    ):
        existing_data = dict(
            active_state.data
            or {}
        )

        existing_analysis = (
            analyze_project_creation(
                existing_data
            )
        )

        if (
            existing_analysis[
                "complete"
            ]
            and is_confirmation(
                normalized_text
            )
        ):
            project = (
                build_project_from_creation_data(
                    existing_data
                )
            )

            project_repository.save_project(
                project
            )

            clear_active_conversation(
                user_key
            )

            return {
                "analysis": (
                    existing_analysis
                ),
                "data": (
                    existing_data
                ),
                "project": project,
                "answer": (
                    f"Projekt {project['id']} "
                    f"— {project['name']} "
                    "er oprettet som udkast."
                ),
            }

        new_data = parse_followup_answer(
            normalized_text,
            existing_data,
            default_year=resolved_year,
        )

        merged_data = merge_data(
            existing_data,
            new_data,
        )

        analysis = (
            analyze_project_creation(
                merged_data
            )
        )

        # Dialogtilstanden bevares også når alle
        # oplysninger er til stede. Først efter
        # eksplicit bekræftelse oprettes projektet
        # og conversation state ryddes.
        save_active_conversation(
            workflow=(
                PROJECT_CREATION_WORKFLOW
            ),
            data=merged_data,
            user_key=user_key,
        )

        return {
            "analysis": analysis,
            "data": merged_data,
            "answer": (
                format_project_creation_analysis(
                    analysis,
                    updated_fields=list(
                        new_data.keys()
                    ),
                )
            ),
        }

    parsed = (
        parse_project_creation_request(
            normalized_text,
            default_year=resolved_year,
        )
    )

    data = clean_data(
        parsed
    )

    analysis = (
        analyze_project_creation(
            data
        )
    )

    save_active_conversation(
        workflow=(
            PROJECT_CREATION_WORKFLOW
        ),
        data=data,
        user_key=user_key,
    )

    return {
        "analysis": analysis,
        "data": data,
        "answer": (
            format_project_creation_analysis(
                analysis,
                updated_fields=[],
            )
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
