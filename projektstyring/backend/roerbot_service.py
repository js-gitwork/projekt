import json
import re
from pathlib import Path

from core.ai_assistent import ask_mistral
from projektstyring.backend.project_repository import ProjectRepository


repo = ProjectRepository()

BEGREBER_PATH = Path("projektstyring/data/roerbot_begreber.json")


def load_roerbot_begreber():
    if not BEGREBER_PATH.exists():
        return {}

    with open(BEGREBER_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def value_of(item, key, default=""):
    if isinstance(item, dict):
        return item.get(key, default)

    return getattr(item, key, default)


def normalize_project(project):
    return {
        "id": value_of(project, "id"),
        "name": value_of(project, "name"),
        "customer": value_of(project, "customer"),
        "city": value_of(project, "city"),
        "status": value_of(project, "status"),
        "start_date": str(value_of(project, "start_date")),
    }


def get_all_projects():
    return [
        normalize_project(project)
        for project in repo.list_projects()
    ]


def get_project(project_id):
    return repo.load_project(project_id)


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


def extract_project_id(text):
    match = re.search(r"\bV\d+\b", text.upper())

    if not match:
        return None

    return match.group(0)


def choose_tool(question):
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
                "project_id": "V-nummer, fx V165460"
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
- Vælg get_project hvis brugeren nævner et konkret V-nummer.
- Vælg general_answer hvis intet tool passer sikkert.
- Opfind aldrig projekt-id.

Spørgsmål:
{question}

Svarformat:
{{
  "tool": "tool_navn",
  "args": {{}}
}}
"""

    raw_answer = ask_mistral(
        prompt,
        model="mistral-small-latest",
    )

    try:
        return json.loads(raw_answer)
    except json.JSONDecodeError:
        return {
            "tool": "general_answer",
            "args": {},
        }


def build_general_prompt(question):
    roerbot_begreber = load_roerbot_begreber()
    projects = get_all_projects()

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

    tool_call = choose_tool(question)
    tool_name = tool_call.get("tool")
    args = tool_call.get("args", {})

    if tool_name == "get_all_projects":
        projects = get_all_projects()

        return {
            "answer": format_projects(projects)
        }

    if tool_name == "get_project":
        project_id = args.get("project_id") or extract_project_id(question)

        if not project_id:
            return {
                "answer": "Jeg mangler projekt-id. Skriv fx V165460."
            }

        project = get_project(project_id)

        return {
            "answer": format_project(project)
        }

    prompt = build_general_prompt(question)

    answer = ask_mistral(
        prompt,
        model="mistral-small-latest",
    )

    return {
        "answer": answer
    }