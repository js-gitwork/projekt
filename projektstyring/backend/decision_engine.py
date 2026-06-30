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

        if project_id in overrides:
            project_data = overrides[project_id]
        else:
            project_data = repo.load_project(project_id)

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
        overrides={
            project_id: simulated_project,
        }
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