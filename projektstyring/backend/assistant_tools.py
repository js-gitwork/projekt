from projektstyring.backend.conversation_engine import (
    handle_project_creation_message,
)
from projektstyring.backend.decision_engine import (
    simulate_project_start_change,
    simulate_team_deadline_goal,
    simulate_workflow_exception,
)
from projektstyring.backend.decision_executor import approve_decision
from projektstyring.backend.decision_parser import build_decision_data
from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.repositories.conversation_state_repository import (
    clear_active_conversation,
    get_active_conversation,
    save_active_conversation,
)
from projektstyring.backend.roerbot_project_insight import build_project_insight


repo = ProjectRepository()


def value_of(item, key, default=""):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def missing_decision_fields(data):
    missing = []

    if not data.get("project_id"):
        missing.append("project_id")

    if not data.get("task_type"):
        missing.append("task_type")

    if not data.get("deadline"):
        missing.append("deadline")

    return missing


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


def run_simulate_project_start_change(project_id: str, new_start_date: str):
    return simulate_project_start_change(project_id, new_start_date)


def start_project_decision_dialog(question: str, intent: dict):
    data = build_decision_data(question, intent)
    missing = missing_decision_fields(data)

    save_active_conversation(
        workflow="pending_project_decision",
        data={
            **data,
            "missing": missing,
        },
        user_key="default",
    )

    if missing:
        return {
            "answer": (
                "Det lyder som en projektlederbeslutning, ikke bare et "
                "almindeligt spørgsmål.\n\n"
                "Jeg mangler stadig: "
                + ", ".join(missing)
                + "."
            )
        }

    return continue_pending_project_decision(question)


def continue_pending_project_decision(question: str):
    active_state = get_active_conversation("default")

    if not active_state:
        return {
            "answer": "Jeg har ingen aktiv beslutningsdialog at fortsætte."
        }

    data = value_of(active_state, "data", {}) or {}

    original_question = data.get("original_question", "").strip()
    current_question = question.strip()

    if current_question == original_question:
        combined_question = original_question
    else:
        combined_question = f"{original_question}\n{current_question}".strip()

    updated_data = {
        **data,
        **{
            key: value
            for key, value in build_decision_data(
                combined_question,
                data.get("intent", {}),
            ).items()
            if value is not None
        },
    }

    missing = missing_decision_fields(updated_data)

    if missing:
        save_active_conversation(
            workflow="pending_project_decision",
            data={
                **updated_data,
                "missing": missing,
            },
            user_key="default",
        )

        return {
            "answer": (
                "Jeg mangler stadig: "
                + ", ".join(missing)
                + "."
            )
        }

    if updated_data.get("deadline") and updated_data.get("team"):
        result = simulate_team_deadline_goal(
            updated_data["project_id"],
            task_type=updated_data["task_type"],
            deadline=updated_data["deadline"],
            team=updated_data.get("team"),
            reason=updated_data["reason"],
        )
    else:
        result = simulate_workflow_exception(
            updated_data["project_id"],
            task_type=updated_data["task_type"],
            before_task_type=updated_data.get("before_task_type"),
            deadline=updated_data.get("deadline"),
            team=updated_data.get("team"),
            reason=updated_data["reason"],
        )

    simulation = result["simulation"]
    change = simulation.get("change", {})
    decision_type = change.get("type")

    if decision_type == "team_deadline_goal":
        save_active_conversation(
            workflow="pending_solution_choice",
            data={
                "simulation": simulation,
            },
            user_key="default",
        )

        return {
            "answer": (
                result["answer"]
                + "\n\n"
                "Vælg først hvilken løsning du vil arbejde videre med, "
                "fx feriearbejde, lørdagsarbejde, ekstra hold eller "
                "workflow-undtagelse."
            )
        }

    save_active_conversation(
        workflow="pending_decision_approval",
        data={
            "simulation": simulation,
        },
        user_key="default",
    )

    return {
        "answer": (
            result["answer"]
            + "\n\n"
            "Vil du godkende denne ændring? "
            "Skriv fx: Godkendt af Jacob."
        )
    }


def extract_approved_by(question: str):
    original = question.strip()
    lower = original.lower()

    prefixes = [
        "godkendt af ",
        "godkend af ",
        "godkendt ",
    ]

    for prefix in prefixes:
        if lower.startswith(prefix):
            return original[len(prefix):].strip() or None

    return None


def approve_pending_decision(question: str):
    active_state = get_active_conversation("default")

    if not active_state:
        return {
            "answer": "Jeg har ingen afventende beslutning at godkende."
        }

    data = value_of(active_state, "data", {}) or {}
    simulation = data.get("simulation")
    approved_by = extract_approved_by(question)

    if not approved_by:
        return {
            "answer": (
                "Jeg mangler navn på projektlederen. "
                "Skriv fx: Godkendt af Jacob."
            )
        }

    result = approve_decision(
        simulation=simulation,
        approved_by=approved_by,
    )

    if result.get("ok"):
        clear_active_conversation("default")

    return {
        "answer": result["answer"]
    }


def project_is_planning_phase(project):
    status = value_of(project, "status", "").lower()
    return status in {"planning", "survey", "upcoming"}


def update_project_status(project_id: str, status: str):
    project = repo.load_project(project_id)

    if not project_is_planning_phase(project):
        return {
            "answer": (
                f"Projekt {value_of(project, 'id')} — "
                f"{value_of(project, 'name')} "
                f"har status '{value_of(project, 'status')}'.\n\n"
                f"Jeg kan foreslå at ændre status til '{status}', men jeg "
                "ændrer ikke projektet uden projektlederens godkendelse."
            ),
            "requires_approval": True,
            "project_id": project_id,
            "proposed_status": status,
        }

    updated_project = repo.update_project_status(project_id, status)

    return {
        "answer": (
            f"Projekt {updated_project['id']} — {updated_project['name']} "
            f"er nu sat til status: {status}."
        ),
        "project": updated_project,
    }


def update_project_fields(project_id: str, updates: dict):
    project = repo.load_project(project_id)

    if not project_is_planning_phase(project):
        return {
            "answer": (
                f"Projekt {value_of(project, 'id')} — "
                f"{value_of(project, 'name')} "
                f"har status '{value_of(project, 'status')}'.\n\n"
                "Jeg kan foreslå ændringen og analysere konsekvenserne, men "
                "jeg ændrer ikke projektet uden projektlederens godkendelse."
            ),
            "requires_approval": True,
            "project_id": project_id,
            "proposed_updates": updates,
        }

    updated_project = repo.update_project_fields(project_id, updates)

    return {
        "answer": (
            f"Projekt {updated_project['id']} — {updated_project['name']} "
            "er opdateret."
        ),
        "project": updated_project,
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
    "simulate_team_deadline_goal": simulate_team_deadline_goal,
    "simulate_workflow_exception": simulate_workflow_exception,
    "start_project_decision_dialog": start_project_decision_dialog,
    "continue_pending_project_decision": continue_pending_project_decision,
    "approve_pending_decision": approve_pending_decision,
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