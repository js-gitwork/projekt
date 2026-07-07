from projektstyring.backend.conversation_engine import (
    handle_project_creation_message,
)
from projektstyring.backend.decision_engine import (
    simulate_project_start_change,
    simulate_workflow_exception,
)
from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.roerbot_project_insight import build_project_insight
from projektstyring.backend.repositories.conversation_state_repository import (
    clear_active_conversation,
    save_active_conversation,
)


repo = ProjectRepository()


def value_of(item, key, default=""):
    if isinstance(item, dict):
        return item.get(key, default)

    return getattr(item, key, default)


def extract_project_id(text):
    for word in text.replace(",", " ").replace(".", " ").split():
        cleaned = word.strip().upper()
        if cleaned.startswith("V") and any(char.isdigit() for char in cleaned):
            return cleaned

    return None


def get_all_projects():
    projects = repo.list_projects()

    return [
        {
            "id": value_of(project, "id"),
            "name": value_of(project, "name"),
            "customer": value_of(project, "customer"),
            "city": value_of(project, "city"),
            "status": value_of(project, "status"),
            "start_date": str(value_of(project, "start_date")),
        }
        for project in projects
    ]


def get_project(project_id: str):
    return repo.load_project(project_id)


def get_project_insight(project_id: str):
    project = repo.load_project(project_id)
    return build_project_insight(project)


def run_simulate_project_start_change(
    project_id: str,
    new_start_date: str,
):
    return simulate_project_start_change(
        project_id,
        new_start_date,
    )


def start_project_decision_dialog(question: str, intent: dict):
    project_id = extract_project_id(question)

    if not project_id and "herslev" in question.lower():
        project_id = "V165460"

    if not project_id:
        save_active_conversation(
            workflow="pending_project_decision",
            data={
                "intent": intent,
                "original_question": question,
                "missing": ["project_id"],
            },
            user_key="default",
        )

        return {
            "answer": (
                "Det lyder som en projektlederbeslutning, ikke bare et "
                "almindeligt spørgsmål.\n\n"
                "Jeg mangler projekt-id, før jeg kan analysere konsekvenserne. "
                "Skriv fx: Projekt id V165460."
            )
        }

    save_active_conversation(
        workflow="pending_project_decision",
        data={
            "intent": intent,
            "original_question": question,
            "project_id": project_id,
            "missing": [],
        },
        user_key="default",
    )

    return continue_pending_project_decision(
        question=f"Projekt id {project_id}"
    )


def continue_pending_project_decision(question: str):
    project_id = extract_project_id(question)

    if not project_id:
        return {
            "answer": (
                "Jeg mangler stadig projekt-id. "
                "Skriv fx: Projekt id V165460."
            )
        }

    clear_active_conversation("default")

    result = simulate_workflow_exception(
        project_id,
        task_type="korthat",
        before_task_type="hovedledning",
        deadline="2026-08-02",
        team="stik2",
        reason="Stik2 skal videre til Sjælland fra uge 32.",
    )

    return {
        "answer": result["answer"]
    }


def update_project_status(
    project_id: str,
    status: str,
):
    project = repo.update_project_status(
        project_id,
        status,
    )

    return {
        "answer": (
            f"Projekt {project['id']} — {project['name']} "
            f"er nu sat til status: {status}."
        ),
        "project": project,
    }


def update_project_fields(project_id: str, updates: dict):
    project = repo.update_project_fields(project_id, updates)

    return {
        "answer": (
            f"Projekt {project['id']} — {project['name']} "
            "er opdateret."
        ),
        "project": project,
    }


def analyze_project_creation_request(question: str):
    return handle_project_creation_message(
        question,
        default_year=2026,
        user_key="default",
    )


TOOLS = {
    "get_all_projects": get_all_projects,
    "get_project": get_project,
    "simulate_project_start_change": run_simulate_project_start_change,
    "simulate_workflow_exception": simulate_workflow_exception,
    "start_project_decision_dialog": start_project_decision_dialog,
    "continue_pending_project_decision": continue_pending_project_decision,
    "analyze_project_creation_request": analyze_project_creation_request,
    "update_project_status": update_project_status,
    "update_project_fields": update_project_fields,
    "get_project_insight": get_project_insight,
}


def run_tool(tool_name: str, args: dict | None = None):
    args = args or {}

    if tool_name not in TOOLS:
        return {
            "error": f"Ukendt tool: {tool_name}",
            "available_tools": list(TOOLS.keys()),
        }

    return TOOLS[tool_name](**args)


def available_tools():
    return list(TOOLS.keys())