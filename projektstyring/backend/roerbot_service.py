import json
import re
from pathlib import Path

from core.ai_assistent import ask_mistral, ask_mistral_fast
from projektstyring.backend.assistant_tools import run_tool
from projektstyring.backend.repositories.conversation_state_repository import (
    get_active_conversation,
)
from projektstyring.backend.conversation_router import route_conversation


BEGREBER_PATH = Path("projektstyring/data/roerbot_begreber.json")


def load_roerbot_begreber():
    if not BEGREBER_PATH.exists():
        return {}

    with open(BEGREBER_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def extract_project_id(text):
    match = re.search(r"\bV\d+\b", text.upper())

    if not match:
        return None

    return match.group(0)


def extract_date(text):
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)

    if not match:
        return None

    return match.group(0)


def format_projects(projects):
    if not projects:
        return "Jeg kunne ikke finde nogen projekter."

    lines = [
        f"• {project['id']} — {project['name']}"
        for project in projects
    ]

    return (
        f"Vi har {len(projects)} projekter:\n\n"
        + "\n".join(lines)
    )

def extract_installation_id(question):
    patterns = [
        r"\binstallation\s+(?:nr\.?\s*)?([a-z0-9_-]+)\b",
        r"\binst(?:allation)?\.?\s*(?:nr\.?\s*)?([a-z0-9_-]+)\b",
    ]

    lower = question.lower()

    for pattern in patterns:
        match = re.search(
            pattern,
            lower,
            flags=re.IGNORECASE,
        )

        if match:
            return match.group(1)

    return None


def is_installation_question(question):
    lower = question.lower()

    installation_id = extract_installation_id(
        question
    )

    if not installation_id:
        return False

    question_phrases = [
        "hvor langt",
        "status",
        "fremdrift",
        "hvor meget",
        "hvordan går",
        "hvad mangler",
        "færdig",
        "faerdig",
        "progress",
    ]

    return any(
        phrase in lower
        for phrase in question_phrases
    )


def format_percent(value):
    if value is None:
        return "Ikke oplyst"

    number = float(value)

    if number.is_integer():
        return f"{int(number)} %"

    return f"{number:.1f} %"


def format_installation_progress(data):
    if data.get("error"):
        return data["error"]

    progress = data.get("progress") or {}

    lines = [
        (
            f"Installation {data['installation_id']} "
            f"i {data['project_id']} — "
            f"{data.get('project_name', '')}"
        ),
        "",
        (
            "Opmåling: "
            + format_percent(
                progress.get("opmaaling")
            )
        ),
        (
            "Forarbejde: "
            + format_percent(
                progress.get("forarbejde")
            )
        ),
        (
            "Stikopmåling: "
            + format_percent(
                progress.get("stikopmaaling")
            )
        ),
        (
            "Hovedledning: "
            + format_percent(
                progress.get("hovedledning")
            )
        ),
        (
            "Stikåbning: "
            + format_percent(
                progress.get("stikaabning")
            )
        ),
        "",
        f"Forventede stik: {data.get('expected_stik', 0)}",
        f"Aktive stik: {data.get('active_stik', 0)}",
        f"Genåbnede stik: {data.get('opened_stik', 0)}",
    ]

    if data.get("hoveddato"):
        lines.append(
            f"Hovedledning planlagt: {data['hoveddato']}"
        )

    assignments = data.get("assignments") or []

    if assignments:
        lines.append("")
        lines.append("Tildelte opgaver:")

        for assignment in assignments:
            lines.append(
                f"• {assignment['task_type']} "
                f"— {assignment['team']}"
            )

    if data.get("notes"):
        lines.extend(
            [
                "",
                f"Bemærkning: {data['notes']}",
            ]
        )

    return "\n".join(lines)

def format_project(project):
    if not project:
        return "Jeg kunne ikke finde projektet."

    installations = project.get("installations", [])
    task_assignments = project.get("task_assignments", {})

    assigned_teams = sorted({
        assignment.get("team")
        for task_groups in task_assignments.values()
        for assignment in task_groups
        if assignment.get("team")
    })

    active_installations = [
        installation
        for installation in installations
        if installation.get("active", True)
    ]

    lines = [
        f"Projekt {project.get('id')} — {project.get('name')}",
        "",
        f"Kunde: {project.get('customer', '')}",
        f"By: {project.get('city', '')}",
        f"Status: {project.get('status', '')}",
        f"Startdato: {project.get('start_date', '')}",
        "",
        f"Installationer: {len(installations)}",
        f"Aktive installationer: {len(active_installations)}",
        f"Tildelte hold: {len(assigned_teams)}",
    ]

    if assigned_teams:
        lines.append("")
        lines.append("Hold:")

        for team in assigned_teams:
            lines.append(f"• {team}")

    return "\n".join(lines)


def is_project_creation_request(question):
    lower = question.strip().lower()

    return (
        "opret projekt" in lower
        or "opret nyt projekt" in lower
        or lower.startswith("opret v")
    )


def is_status_change_request(question):
    lower = question.strip().lower()

    status_words = [
        "opmålt",
        "opmaalt",
        "klar til planlægning",
        "klar til planlaegning",
        "kommende",
        "i gang",
        "igang",
        "aktiv",
        "afsluttet",
        "færdig",
        "faerdig",
        "mangler opmåling",
        "mangler opmaaling",
    ]

    return extract_project_id(question) and any(
        word in lower
        for word in status_words
    )


def normalize_project_status(text, raw_status=None):
    value = (raw_status or "").strip().lower()
    lower = text.strip().lower()

    status_aliases = {
        "survey": "survey",
        "opmåling": "survey",
        "opmaaling": "survey",
        "mangler opmåling": "survey",
        "mangler opmaaling": "survey",

        "upcoming": "upcoming",
        "kommende": "upcoming",
        "klar": "upcoming",
        "klar til planlægning": "upcoming",
        "klar til planlaegning": "upcoming",
        "opmålt": "upcoming",
        "opmaalt": "upcoming",

        "active": "active",
        "aktiv": "active",
        "i gang": "active",
        "igang": "active",

        "completed": "completed",
        "afsluttet": "completed",
    }

    if value in status_aliases:
        return status_aliases[value]

    if lower in status_aliases:
        return status_aliases[lower]

    status_phrases = {
        "sæt projektet til": status_aliases,
        "saet projektet til": status_aliases,
        "ændr projektet til": status_aliases,
        "aendr projektet til": status_aliases,
        "marker projektet som": status_aliases,
        "sæt status til": status_aliases,
        "saet status til": status_aliases,
        "ændr status til": status_aliases,
        "aendr status til": status_aliases,
    }

    for prefix, aliases in status_phrases.items():
        if lower.startswith(prefix):
            rest = lower.replace(prefix, "", 1).strip()
            return aliases.get(rest)

    return None


def choose_tool(question):
    active_state = get_active_conversation("default")

    project_id = extract_project_id(question)
    installation_id = extract_installation_id(
        question
    )

    if (
        project_id
        and installation_id
        and is_installation_question(question)
    ):
        return {
            "tool": "get_installation_progress",
            "args": {
                "project_id": project_id,
                "installation_id": installation_id,
            },
        }

    if active_state and active_state.workflow == "project_creation":
        return {
            "tool": "analyze_project_creation_request",
            "args": {
                "question": question,
            },
        }

    if is_project_creation_request(question):
        return {
            "tool": "analyze_project_creation_request",
            "args": {
                "question": question,
            },
        }

    if is_status_change_request(question):
        return {
            "tool": "update_project_status",
            "args": {
                "project_id": extract_project_id(question),
                "status": None,
            },
        }

    tools = [
        {
            "tool": "get_all_projects",
            "description": "Bruges når brugeren spørger hvilke projekter, sager eller opgaver der findes i systemet.",
            "args": {},
        },
        {
            "tool": "get_project",
            "description": "Bruges når brugeren spørger om et bestemt projekt-id.",
            "args": {
                "project_id": "V-nummer, fx V165460",
            },
        },
        {
            "tool": "simulate_project_start_change",
            "description": (
                "Bruges når brugeren vil simulere eller konsekvensberegne "
                "en ændret startdato for et projekt."
            ),
            "args": {
                "project_id": "V-nummer, fx V165460",
                "new_start_date": "Ny startdato i formatet YYYY-MM-DD",
            },
        },
        {
            "tool": "update_project_status",
            "description": (
                "Bruges når brugeren vil ændre status på et projekt, "
                "fx markere det som opmålt, kommende, aktivt eller afsluttet."
            ),
            "args": {
                "project_id": "V-nummer, fx V165930",
                "status": "survey, upcoming, active eller completed",
            },
        },
        {
            "tool": "general_answer",
            "description": "Bruges til faglige spørgsmål, forklaringer eller spørgsmål hvor der ikke findes et sikkert tool.",
            "args": {},
        },
    ]

    prompt = f"""
Du skal vælge hvilket tool Roerbot skal bruge.

Returnér KUN gyldig JSON.
Ingen forklaring.
Ingen markdown.

Mulige tools:
{json.dumps(tools, indent=2, ensure_ascii=False)}

Regler:
- Vælg get_all_projects hvis brugeren spørger efter en liste over projekter/sager/opgaver.
- Vælg get_project hvis brugeren nævner et konkret V-nummer og blot spørger om projektet.
- Vælg simulate_project_start_change hvis brugeren vil simulere, flytte, ændre startdato eller konsekvensberegne et projekt.
- Vælg update_project_status hvis brugeren vil ændre projektets status.
- Vælg general_answer hvis intet tool passer sikkert.
- Opfind aldrig projekt-id.
- Opfind aldrig datoer.

Spørgsmål:
{question}

Svarformat:
{{
  "tool": "tool_navn",
  "args": {{}}
}}
"""

    raw_answer = ask_mistral_fast(prompt)

    try:
        return json.loads(raw_answer)
    except json.JSONDecodeError:
        return {
            "tool": "general_answer",
            "args": {},
        }


def build_general_prompt(question):
    roerbot_begreber = load_roerbot_begreber()
    projects = run_tool("get_all_projects")

    return f"""
Du er Roerbot, global projektassistent for strømpeforingsprojekter.

Vigtige regler:
- Du må ikke opfinde projektdata.
- Hvis spørgsmålet kræver et bestemt projekt, og brugeren ikke har angivet projekt-id, skal du bede om projekt-id.
- Ved konkrete tal skal du kun bruge projektdata.
- Ved faglige begreber må du bruge virksomhedens begreber og generel faglig viden.
- Svar kort og præcist.

Virksomhedens begreber:
{json.dumps(roerbot_begreber, indent=2, ensure_ascii=False)}

Tilgængelige projekter:
{json.dumps(projects, indent=2, ensure_ascii=False)}

Spørgsmål:
{question}
"""


def ask_roerbot(question):
    question = question.strip()

    if not question:
        return {
            "answer": "Du skal skrive et spørgsmål."
        }

    route = route_conversation(question)

    if route["route"] == "tool":
        result = run_tool(
            route["tool"],
            route.get("args", {}),
        )

        return {
            "answer": result["answer"]
        }

    tool_call = choose_tool(question)
    tool_name = tool_call.get("tool")
    args = tool_call.get("args", {})

    if tool_name == "analyze_project_creation_request":
        result = run_tool(
            "analyze_project_creation_request",
            {
                "question": question,
            },
        )

        return {
            "answer": result["answer"]
        }

    if tool_name == "get_all_projects":
        projects = run_tool("get_all_projects")

        return {
            "answer": format_projects(projects)
        }

    if tool_name == "get_installation_progress":
        project_id = (
            args.get("project_id")
            or extract_project_id(question)
        )
        installation_id = (
            args.get("installation_id")
            or extract_installation_id(question)
        )

        if not project_id:
            return {
                "answer": (
                    "Jeg mangler projekt-id. "
                    "Skriv fx V165460."
                )
            }

        if not installation_id:
            return {
                "answer": (
                    "Jeg mangler installationsnummeret."
                )
            }

        result = run_tool(
            "get_installation_progress",
            {
                "project_id": project_id,
                "installation_id": installation_id,
            },
        )

        return {
            "answer": format_installation_progress(
                result
            )
        }

    if tool_name == "get_project":
        project_id = args.get("project_id") or extract_project_id(question)

        if not project_id:
            return {
                "answer": "Jeg mangler projekt-id. Skriv fx V165460."
            }

        project = run_tool(
            "get_project",
            {"project_id": project_id},
        )

        return {
            "answer": format_project(project)
        }

    if tool_name == "simulate_project_start_change":
        project_id = (
            args.get("project_id")
            or extract_project_id(question)
        )
        new_start_date = (
            args.get("new_start_date")
            or extract_date(question)
        )

        if not project_id:
            return {
                "answer": "Jeg mangler projekt-id. Skriv fx V165460."
            }

        if not new_start_date:
            return {
                "answer": "Jeg mangler ny startdato. Brug formatet YYYY-MM-DD."
            }

        result = run_tool(
            "simulate_project_start_change",
            {
                "project_id": project_id,
                "new_start_date": new_start_date,
            },
        )

        return {
            "answer": result["answer"]
        }

    if tool_name == "update_project_status":
        project_id = (
            args.get("project_id")
            or extract_project_id(question)
        )
        status = normalize_project_status(
            question,
            args.get("status"),
        )

        if not project_id:
            return {
                "answer": "Jeg mangler projekt-id. Skriv fx V165930."
            }

        if not status:
            return {
                "answer": (
                    "Jeg kunne ikke afgøre status. Brug fx "
                    "opmåling, kommende, i gang eller afsluttet."
                )
            }

        result = run_tool(
            "update_project_status",
            {
                "project_id": project_id,
                "status": status,
            },
        )

        return {
            "answer": result["answer"]
        }

    prompt = build_general_prompt(question)
    answer = ask_mistral(prompt)

    return {
        "answer": answer
    }