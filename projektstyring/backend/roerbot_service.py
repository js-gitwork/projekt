import json
import re
from pathlib import Path

from core.ai_assistent import ask_mistral
from projektstyring.backend.assistant_tools import run_tool


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
            "tool": "simulate_project_start_change",
            "description": (
                "Bruges når brugeren vil simulere eller konsekvensberegne "
                "en ændret startdato for et projekt."
            ),
            "args": {
                "project_id": "V-nummer, fx V165460",
                "new_start_date": "Ny startdato i formatet YYYY-MM-DD"
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

    tool_call = choose_tool(question)
    tool_name = tool_call.get("tool")
    args = tool_call.get("args", {})

    if tool_name == "get_all_projects":
        projects = run_tool("get_all_projects")

        return {
            "answer": format_projects(projects)
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
        project_id = args.get("project_id") or extract_project_id(question)
        new_start_date = args.get("new_start_date") or extract_date(question)

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

    prompt = build_general_prompt(question)

    answer = ask_mistral(
        prompt,
        model="mistral-small-latest",
    )

    return {
        "answer": answer
    }