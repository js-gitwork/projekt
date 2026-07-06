from datetime import date

from projektstyring.backend.project_creation_parser import (
    parse_project_creation_request,
)
from projektstyring.backend.repositories.conversation_state_repository import (
    clear_active_conversation,
    get_active_conversation,
    save_active_conversation,
)
from projektstyring.backend.workflow_engine import (
    PROJECT_CREATION_WORKFLOW,
)
from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.survey_model import default_survey

FIELD_LABELS = {
    "project_id": "V-nummer",
    "name": "Projektnavn",
    "customer": "Kunde",
    "city": "By/område",
    "start_date": "Startdato",
    "installation_count": "Antal installationer",
    "preparation_team": "Forarbejdshold",
}

repo = ProjectRepository()

def clean_data(data):
    return {
        key: value
        for key, value in data.items()
        if value not in [None, ""]
    }


def merge_data(existing_data, new_data):
    merged = dict(existing_data or {})

    for key, value in new_data.items():
        if value not in [None, ""]:
            merged[key] = value

    return merged


def analyze_project_creation(data):
    missing = []
    provided = {}

    for field in PROJECT_CREATION_WORKFLOW:
        value = data.get(field.name)

        if value:
            provided[field.name] = value
        else:
            missing.append(
                {
                    "field": field.name,
                    "label": FIELD_LABELS.get(field.name, field.name),
                    "prompt": field.prompt,
                    "reason": field.reason,
                }
            )

    return {
        "workflow": "project_creation",
        "complete": len(missing) == 0,
        "provided": provided,
        "missing": missing,
        "next_question": missing[0]["prompt"] if missing else None,
    }


def detect_project_creation_start(text):
    lower = text.strip().lower()

    return (
        "opret projekt" in lower
        or "opret nyt projekt" in lower
        or lower.startswith("opret v")
    )


def parse_followup_answer(text, active_data):
    parsed = parse_project_creation_request(text)

    cleaned = clean_data(parsed)

    if cleaned:
        return cleaned

    active_analysis = analyze_project_creation(active_data)
    missing = active_analysis.get("missing", [])

    if not missing:
        return {}

    next_field = missing[0]["field"]
    value = text.strip()

    if not value:
        return {}

    return {
        next_field: value,
    }

def is_confirmation(text):
    return text.strip().lower() in [
        "ja",
        "ja tak",
        "opret",
        "opret projektet",
        "gem",
        "gem projektet",
    ]


def build_project_from_creation_data(data):
    installation_count = int(data.get("installation_count", 0))

    installations = []

    for number in range(1, installation_count + 1):
        installations.append(
            {
                "id": number,
                "active": True,
                "hoveddato": "",
                "expected_stik": 0,
                "active_stik": 0,
                "langhatte": 0,
                "korthatte_extra": 0,
                "broende": 0,
                "notes": "",
            }
        )

    return {
        "id": data.get("project_id"),
        "name": data.get("name"),
        "customer": data.get("customer"),
        "city": data.get("city"),
        "start_date": data.get("start_date"),

        "status": "survey",
        "survey": default_survey(data.get("start_date")),

        "installations": installations,
        "task_assignments": {},
        "notes": "Oprettet som udkast via Roerbot.",
    }

def handle_project_creation_message(
    text,
    default_year=None,
    user_key="default",
):
    default_year = default_year or date.today().year

    active_state = get_active_conversation(user_key)

    if active_state and active_state.workflow == "project_creation":
        existing_data = active_state.data or {}
        analysis = analyze_project_creation(existing_data)

        if analysis["complete"] and is_confirmation(text):
            project = build_project_from_creation_data(existing_data)
            repo.save_project(project)
            clear_active_conversation(user_key)

            return {
                "analysis": analysis,
                "data": existing_data,
                "answer": (
                    f"Projekt {project['id']} — {project['name']} "
                    "er oprettet som udkast."
                ),
            }

    starts_new_project_creation = detect_project_creation_start(text)

    if starts_new_project_creation:
        parsed = parse_project_creation_request(
            text,
            default_year=default_year,
        )
        data = clean_data(parsed)

        save_active_conversation(
            workflow="project_creation",
            data=data,
            user_key=user_key,
        )

        analysis = analyze_project_creation(data)

        return {
            "analysis": analysis,
            "data": data,
            "answer": format_project_creation_analysis(
                analysis,
                updated_fields=[],
            ),
        }

    if active_state and active_state.workflow == "project_creation":
        existing_data = active_state.data or {}

        new_data = parse_followup_answer(
            text,
            existing_data,
        )

        merged_data = merge_data(
            existing_data,
            new_data,
        )

        analysis = analyze_project_creation(merged_data)

        if analysis["complete"]:
            clear_active_conversation(user_key)
        else:
            save_active_conversation(
                workflow="project_creation",
                data=merged_data,
                user_key=user_key,
            )

        return {
            "analysis": analysis,
            "data": merged_data,
            "answer": format_project_creation_analysis(
                analysis,
                updated_fields=list(new_data.keys()),
            ),
        }

    parsed = parse_project_creation_request(
        text,
        default_year=default_year,
    )
    data = clean_data(parsed)
    analysis = analyze_project_creation(data)

    return {
        "analysis": analysis,
        "data": data,
        "answer": format_project_creation_analysis(
            analysis,
            updated_fields=[],
        ),
    }


def analyze_project_creation_text(text, default_year=None):
    result = handle_project_creation_message(
        text,
        default_year=default_year,
    )

    return result["analysis"]


def format_project_creation_analysis(
    analysis,
    updated_fields=None,
):
    updated_fields = updated_fields or []

    lines = [
        "Jeg kan hjælpe med at oprette projektet.",
        "",
    ]

    if updated_fields:
        lines.append("Jeg har opdateret:")

        for field in updated_fields:
            label = FIELD_LABELS.get(field, field)
            value = analysis["provided"].get(field)
            lines.append(f"• {label}: {value}")

        lines.append("")

    if analysis["provided"]:
        lines.append("Jeg har disse oplysninger:")

        for field, value in analysis["provided"].items():
            label = FIELD_LABELS.get(field, field)
            lines.append(f"• {label}: {value}")

    if analysis["missing"]:
        lines.append("")
        lines.append("Jeg mangler:")

        for item in analysis["missing"]:
            line = f"• {item['label']}"

            if item.get("reason"):
                line += f" — {item['reason']}"

            lines.append(line)

        lines.append("")
        lines.append(analysis["next_question"])
    else:
        lines.append("")
        lines.append("Alle nødvendige oplysninger er til stede.")
        lines.append("Skal jeg oprette projektet som udkast?")

    return "\n".join(lines)