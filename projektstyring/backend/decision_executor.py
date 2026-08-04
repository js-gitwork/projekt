from copy import deepcopy
from datetime import datetime
from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.project_planner import generate_plan_for_project
from projektstyring.backend.decision_log import add_decision
from projektstyring.backend.snapshot_service import add_snapshot


repo = ProjectRepository()


SUPPORTED_DECISION_TYPES = {
    "team_deadline_goal",
    "workflow_exception",
    "project_start_change",
}


def ensure_project_rules(project):
    project.setdefault("project_rules", [])
    return project


def require_approved_by(approved_by):
    approved_by = (approved_by or "").strip()

    if not approved_by:
        return None, {
            "ok": False,
            "answer": (
                "Jeg kan ikke godkende ændringen uden navn på projektlederen. "
                "Skriv fx: Godkendt af Jacob."
            ),
        }

    return approved_by, None


def build_project_rule(simulation, approved_by):
    change = simulation.get("change", {})
    decision_type = change.get("type")

    rule = {
        "type": decision_type,
        "approved": True,
        "approved_by": approved_by,
        "approved_at": datetime.now().isoformat(timespec="seconds"),
        "source": "roerbot",
        "change": change,
    }

    if simulation.get("project_id"):
        rule["project_id"] = simulation["project_id"]

    if change.get("reason"):
        rule["reason"] = change["reason"]

    if change.get("deadline"):
        rule["deadline"] = change["deadline"]

    if change.get("team"):
        rule["team"] = change["team"]

    if change.get("task_type"):
        rule["task_type"] = change["task_type"]

    return rule


def apply_decision_to_project(project, simulation, approved_by):
    """
    Gemmer den godkendte beslutning som projektregel.

    Denne funktion bør ikke gætte eller opfinde ændringer.
    Den gemmer kun den beslutning, der allerede er simuleret.
    """

    updated_project = deepcopy(project)
    ensure_project_rules(updated_project)

    rule = build_project_rule(
        simulation=simulation,
        approved_by=approved_by,
    )

    updated_project["project_rules"].append(rule)

    return updated_project, rule


def approve_decision(simulation, approved_by):
    approved_by, error = require_approved_by(approved_by)

    if error:
        return error

    if not simulation:
        return {
            "ok": False,
            "answer": "Jeg mangler en simulation at godkende.",
        }

    project_id = simulation.get("project_id")
    change = simulation.get("change", {})
    decision_type = change.get("type")

    if not project_id:
        return {
            "ok": False,
            "answer": "Simulationen mangler projekt-id.",
        }

    if decision_type not in SUPPORTED_DECISION_TYPES:
        return {
            "ok": False,
            "answer": (
                "Jeg kan ikke godkende denne beslutningstype endnu: "
                f"{decision_type}"
            ),
        }

    project = repo.load_project(project_id)

    add_snapshot(
        project,
        reason=(
            "Før godkendt Roerbot-beslutning "
            f"({decision_type}) — godkendt af {approved_by}"
        ),
    )

    updated_project, rule = apply_decision_to_project(
        project=project,
        simulation=simulation,
        approved_by=approved_by,
    )

    generate_plan_for_project(updated_project)

    add_decision(
        updated_project,
        decision_type=decision_type,
        reason=change.get("reason") or "Godkendt Roerbot-beslutning",
        trigger="roerbot",
        affected_installations=change.get("installation_ids") or [],
        metadata={
            "approved_by": approved_by,
            "approved_at": rule["approved_at"],
            "rule": rule,
            "simulation": simulation,
        },
    )

    add_snapshot(
        updated_project,
        reason=(
            "Efter godkendt Roerbot-beslutning "
            f"({decision_type}) — godkendt af {approved_by}"
        ),
    )

    repo.save_project(updated_project)

    return {
        "ok": True,
        "project": updated_project,
        "rule": rule,
        "answer": (
            f"Beslutningen er godkendt af {approved_by} og gemt på projekt "
            f"{project_id}.\n\n"
            "Der er oprettet snapshot før og efter ændringen, "
            "projektreglen er gemt, planen er valideret, "
            "og beslutningen er logget."
        ),
    }

    updated_project, rule = apply_decision_to_project(
        project=project,
        simulation=simulation,
        approved_by=approved_by,
    )

    # Valider at projektet stadig kan planlægges.
    generate_plan_for_project(updated_project)

    repo.save_project(updated_project)

    create_snapshot(
        project_id=project_id,
        reason=(
            "Efter godkendt Roerbot-beslutning "
            f"({decision_type}) — godkendt af {approved_by}"
        ),
    )

    log_decision(
        project_id=project_id,
        decision_type=decision_type,
        decision=rule,
    )

    return {
        "ok": True,
        "project": updated_project,
        "rule": rule,
        "answer": (
            f"Beslutningen er godkendt af {approved_by} og gemt på projekt "
            f"{project_id}.\n\n"
            "Der er oprettet snapshot før og efter ændringen, "
            "projektreglen er gemt, planen er valideret, "
            "og beslutningen er logget."
        ),
    }