from copy import deepcopy
from datetime import date, timedelta

from projektstyring.backend.conflict_analyzer import find_team_conflicts
from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.project_planner import generate_plan_for_project
from projektstyring.backend.scenario_report import (
    format_scenario_report,
    summarize_scenario,
)


repo = ProjectRepository()


def parse_date(value):
    if not value:
        return None

    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def summarize_plan(result):
    return [
        {
            "installation_id": activity.installation_id,
            "type": str(activity.type),
            "team": activity.hold,
            "start": str(activity.start_dato),
            "end": str(activity.slut_dato),
        }
        for activity in result.activities
    ]


def shift_installation_dates(project, day_delta):
    for installation in project.get("installations", []):
        hoveddato = parse_date(installation.get("hoveddato"))

        if not hoveddato:
            continue

        installation["hoveddato"] = str(
            hoveddato + timedelta(days=day_delta)
        )

    return project


def build_portfolio_plan(overrides=None):
    overrides = overrides or {}
    plans = {}

    for project in repo.list_projects():
        project_id = project.get("id")

        if not project_id:
            continue

        project_data = overrides.get(project_id) or repo.load_project(project_id)
        result = generate_plan_for_project(project_data)
        plans[project_id] = summarize_plan(result)

    return plans


def simulate_project_start_change(project_id, new_start_date):
    original_project = repo.load_project(project_id)

    old_start = parse_date(original_project.get("start_date"))
    new_start = parse_date(new_start_date)

    before_result = generate_plan_for_project(original_project)

    simulated_project = deepcopy(original_project)

    if old_start and new_start:
        day_delta = (new_start - old_start).days
        simulated_project["start_date"] = str(new_start)
        simulated_project = shift_installation_dates(
            simulated_project,
            day_delta,
        )
    else:
        day_delta = 0
        simulated_project["start_date"] = new_start_date

    after_result = generate_plan_for_project(simulated_project)

    portfolio_after = build_portfolio_plan(
        overrides={project_id: simulated_project}
    )

    conflicts = find_team_conflicts(portfolio_after)

    simulation = {
        "project_id": project_id,
        "change": {
            "field": "start_date",
            "from": original_project.get("start_date"),
            "to": new_start_date,
            "day_delta": day_delta,
            "shifted_hoveddato": True,
        },
        "before": summarize_plan(before_result),
        "after": summarize_plan(after_result),
        "conflicts": conflicts,
        "saved": False,
    }

    report = summarize_scenario(simulation)

    return {
        "simulation": simulation,
        "report": report,
        "answer": format_scenario_report(report),
    }


def ensure_workflow_exceptions(project):
    project.setdefault("workflow_exceptions", [])
    return project


def add_workflow_exception(
    project,
    *,
    exception_type,
    task_type,
    installation_ids,
    reason,
    deadline=None,
    team=None,
):
    ensure_workflow_exceptions(project)

    exception = {
        "type": exception_type,
        "task_type": task_type,
        "installation_ids": [str(item) for item in installation_ids],
        "reason": reason,
        "deadline": str(deadline) if deadline else None,
        "team": team,
        "approved": False,
    }

    project["workflow_exceptions"].append(exception)

    return exception


def get_task_dates(plan, task_type):
    return [
        item
        for item in plan
        if item.get("type") == task_type
    ]


def find_workflow_breaks(plan, task_type, before_task_type):
    by_installation = {}

    for item in plan:
        by_installation.setdefault(
            item["installation_id"],
            {},
        )[item["type"]] = item

    breaks = []

    for installation_id, tasks in by_installation.items():
        task = tasks.get(task_type)
        before_task = tasks.get(before_task_type)

        if not task or not before_task:
            continue

        task_start = parse_date(task.get("start"))
        before_end = parse_date(before_task.get("end"))

        if task_start and before_end and task_start < before_end:
            breaks.append(
                {
                    "installation_id": installation_id,
                    "task_type": task_type,
                    "task_start": str(task_start),
                    "before_task_type": before_task_type,
                    "before_task_end": str(before_end),
                }
            )

    return breaks


def simulate_workflow_exception(
    project_id,
    *,
    task_type,
    before_task_type,
    deadline=None,
    team=None,
    reason="Manuel projektlederbeslutning",
):
    """
    Simulerer en bevidst afvigelse fra normal workflowrækkefølge.

    Gemmer ikke noget.
    Bruges som beslutningsgrundlag før projektlederen godkender ændringen.
    """

    original_project = repo.load_project(project_id)

    before_result = generate_plan_for_project(original_project)
    before_plan = summarize_plan(before_result)

    simulated_project = deepcopy(original_project)

    relevant_installation_ids = sorted(
        {
            item["installation_id"]
            for item in before_plan
            if item["type"] == task_type
        },
        key=lambda value: int(value) if str(value).isdigit() else str(value),
    )

    add_workflow_exception(
        simulated_project,
        exception_type="allow_task_before_dependency",
        task_type=task_type,
        installation_ids=relevant_installation_ids,
        reason=reason,
        deadline=deadline,
        team=team,
    )

    after_result = generate_plan_for_project(simulated_project)
    after_plan = summarize_plan(after_result)

    workflow_breaks = find_workflow_breaks(
        after_plan,
        task_type=task_type,
        before_task_type=before_task_type,
    )

    portfolio_after = build_portfolio_plan(
        overrides={project_id: simulated_project}
    )

    conflicts = find_team_conflicts(portfolio_after)

    simulation = {
        "project_id": project_id,
        "change": {
            "type": "workflow_exception",
            "exception_type": "allow_task_before_dependency",
            "task_type": task_type,
            "before_task_type": before_task_type,
            "deadline": str(deadline) if deadline else None,
            "team": team,
            "reason": reason,
        },
        "before": before_plan,
        "after": after_plan,
        "workflow_breaks": workflow_breaks,
        "conflicts": conflicts,
        "saved": False,
    }

    return {
        "simulation": simulation,
        "answer": format_workflow_exception_answer(simulation),
    }


def format_workflow_exception_answer(simulation):
    change = simulation["change"]
    breaks = simulation.get("workflow_breaks", [])
    conflicts = simulation.get("conflicts", [])

    lines = [
        f"Scenario for projekt {simulation['project_id']}",
        "",
        "Ændring:",
        f"- Opgave: {change['task_type']}",
        f"- Tillades før: {change['before_task_type']}",
        f"- Begrundelse: {change['reason']}",
    ]

    if change.get("deadline"):
        lines.append(f"- Deadline: {change['deadline']}")

    if change.get("team"):
        lines.append(f"- Hold: {change['team']}")

    lines.extend(["", "Vurdering:"])

    if breaks:
        lines.append(
            f"- Planen indeholder {len(breaks)} bevidste workflow-afvigelser."
        )
    else:
        lines.append(
            "- Planen indeholder ingen registrerede workflow-afvigelser."
        )

    if conflicts:
        lines.append(f"- Der er {len(conflicts)} holdkonflikter.")
    else:
        lines.append("- Der er ingen registrerede holdkonflikter.")

    lines.extend(
        [
            "",
            "Bemærk:",
            "Dette er kun en simulering. Projektet er ikke ændret.",
            "En sådan afvigelse bør først gemmes efter projektlederens godkendelse.",
        ]
    )

    return "\n".join(lines)