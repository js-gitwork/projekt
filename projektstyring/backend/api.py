from datetime import date

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from projektstyring.backend.project_planner import (
    generate_plan_for_project,
    generate_plan_for_active_projects,
)
from projektstyring.backend.project_operations import add_installations
from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.project_writer import save_project
from projektstyring.backend.team_loader import load_teams


app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory="projektstyring/frontend/static"),
    name="static",
)

templates = Jinja2Templates(
    directory="projektstyring/frontend/templates"
)

repo = ProjectRepository()


TASK_TYPES = [
    "hovedledning",
    "stikforberedelse",
    "stik",
    "kontrol",
    "korthat",
    "broend",
]


def get_teams():
    return load_teams("projektstyring/data/teams.json")


def empty_task_assignments():
    return {
        task_type: []
        for task_type in TASK_TYPES
    }


def ensure_task_assignments(project):
    if "task_assignments" not in project:
        project["task_assignments"] = empty_task_assignments()

    for task_type in TASK_TYPES:
        project["task_assignments"].setdefault(task_type, [])

    return project


def to_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except ValueError:
        return default


def calculate_project_status(project):
    start_date = project.get("start_date")

    if not start_date:
        return "upcoming"

    try:
        if date.fromisoformat(start_date) <= date.today():
            return "active"
    except ValueError:
        return "upcoming"

    return "upcoming"


def installation_sort_key(installation):
    return (
        installation.get("hoveddato") or "9999-12-31",
        to_int(installation.get("id"), 999999),
    )


def activity_sort_key(activity):
    return (
        activity.start_dato or date.max,
        activity.slut_dato or date.max,
        activity.installation_id,
        str(activity.type),
    )


def parse_installation_list(value):
    if not value:
        return []

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def validate_task_assignments(assignments):
    used = {}
    errors = []

    for task_type, rows in assignments.items():
        for row in rows:
            team = row.get("team", "")
            installations = row.get("installations", [])

            for installation_id in installations:
                key = (task_type, installation_id)

                if key in used:
                    errors.append(
                        f"Installation {installation_id} har allerede opgaven "
                        f"{task_type} tildelt til {used[key]} og kan ikke også "
                        f"tildeles til {team}."
                    )
                else:
                    used[key] = team

    return errors


def build_work_cards(activities):
    work_cards = {}

    for activity in activities:
        hold = activity.hold or "Ikke tildelt"

        if hold not in work_cards:
            work_cards[hold] = []

        work_cards[hold].append(activity)

    return {
        hold: sorted(rows, key=activity_sort_key)
        for hold, rows in sorted(work_cards.items())
    }
def build_gantt_data(activities):
    if not activities:
        return {
            "dates": [],
            "rows": [],
        }

    start_dates = [
        activity.start_dato
        for activity in activities
        if activity.start_dato
    ]

    end_dates = [
        activity.slut_dato
        for activity in activities
        if activity.slut_dato
    ]

    if not start_dates or not end_dates:
        return {
            "dates": [],
            "rows": [],
        }

    min_date = min(start_dates)
    max_date = max(end_dates)

    dates = []
    current = min_date

    while current <= max_date:
        dates.append(current)
        current = current.fromordinal(current.toordinal() + 1)

    rows = sorted(
        activities,
        key=lambda activity: (
            activity.start_dato,
            activity.installation_id,
            str(activity.type),
            activity.hold,
        ),
    )

    return {
        "dates": dates,
        "rows": rows,
    }


@app.get("/")
def index(request: Request):
    projects = repo.list_projects()

    return templates.TemplateResponse(
        request,
        "project_list.html",
        {"projects": projects},
    )


@app.get("/plan")
def active_projects_plan(request: Request):
    result = generate_plan_for_active_projects()

    return templates.TemplateResponse(
        request,
        "active_plan.html",
        {
            "result": result,
        },
    )


@app.get("/projects/new")
def new_project_form(request: Request):
    return templates.TemplateResponse(
        request,
        "project_form.html",
        {},
    )


@app.post("/projects/new")
def create_project(
    project_id: str = Form(...),
    name: str = Form(...),
    customer: str = Form(""),
    city: str = Form(""),
    start_date: str = Form(...),
    installation_count: int = Form(0),
):
    project = {
        "id": project_id.strip(),
        "name": name.strip(),
        "customer": customer.strip(),
        "city": city.strip(),
        "start_date": start_date,
        "status": "upcoming",
        "task_assignments": empty_task_assignments(),
        "installations": [],
    }

    project["status"] = calculate_project_status(project)

    if installation_count > 0:
        project = add_installations(
            project,
            installation_count,
        )

    save_project(project)

    return RedirectResponse(
        url="/",
        status_code=303,
    )


@app.get("/projects/{project_id}")
def project_detail(request: Request, project_id: str):
    project = repo.load_project(project_id)

    project["status"] = calculate_project_status(project)
    project = ensure_task_assignments(project)

    project["installations"] = sorted(
        project.get("installations", []),
        key=installation_sort_key,
    )

    save_project(project)

    return templates.TemplateResponse(
        request,
        "project_detail.html",
        {
            "project": project,
            "teams": get_teams(),
            "task_types": TASK_TYPES,
            "errors": [],
        },
    )


@app.post("/projects/{project_id}/save")
async def save_project_detail(request: Request, project_id: str):
    project = repo.load_project(project_id)
    form = await request.form()

    project["customer"] = form.get("customer", "").strip()
    project["city"] = form.get("city", "").strip()
    project["start_date"] = form.get("start_date", "").strip()

    installation_count = to_int(
        form.get("installation_count"),
        0,
    )

    installations = []

    for index in range(installation_count):
        installation_id = form.get(f"id_{index}", "").strip()

        if not installation_id:
            continue

        hoveddato = form.get(f"hoveddato_{index}", "").strip()

        installations.append(
            {
                "id": installation_id,
                "active": form.get(f"active_{index}") == "on",
                "hoveddato": hoveddato or None,
                "expected_stik": to_int(
                    form.get(f"expected_stik_{index}")
                ),
                "active_stik": to_int(
                    form.get(f"active_stik_{index}")
                ),
                "langhatte": to_int(
                    form.get(f"langhatte_{index}")
                ),
                "korthatte_extra": to_int(
                    form.get(f"korthatte_extra_{index}")
                ),
                "broende": to_int(
                    form.get(f"broende_{index}")
                ),
                "notes": form.get(f"notes_{index}", "").strip(),
            }
        )

    assignments = empty_task_assignments()

    assignment_count = to_int(
        form.get("assignment_count"),
        0,
    )

    for index in range(assignment_count):
        task_type = form.get(f"assignment_task_{index}", "").strip()
        team = form.get(f"assignment_team_{index}", "").strip()
        installation_list = form.get(
            f"assignment_installations_{index}",
            "",
        ).strip()

        if not task_type or not team or not installation_list:
            continue

        if task_type not in assignments:
            continue

        assignments[task_type].append(
            {
                "team": team,
                "installations": parse_installation_list(
                    installation_list
                ),
            }
        )

    installations.sort(
        key=installation_sort_key,
    )

    project["installations"] = installations
    project["task_assignments"] = assignments
    project["status"] = calculate_project_status(project)

    errors = validate_task_assignments(assignments)

    if errors:
        return templates.TemplateResponse(
            request,
            "project_detail.html",
            {
                "project": project,
                "teams": get_teams(),
                "task_types": TASK_TYPES,
                "errors": errors,
            },
            status_code=400,
        )

    save_project(project)

    return RedirectResponse(
        url=f"/projects/{project_id}",
        status_code=303,
    )


@app.post("/projects/{project_id}/installations/add")
def add_project_installations(
    project_id: str,
    installation_count: int = Form(...),
):
    project = repo.load_project(project_id)

    project = add_installations(
        project,
        installation_count,
    )

    project = ensure_task_assignments(project)

    project["installations"] = sorted(
        project.get("installations", []),
        key=installation_sort_key,
    )

    project["status"] = calculate_project_status(project)

    save_project(project)

    return RedirectResponse(
        url=f"/projects/{project_id}",
        status_code=303,
    )


@app.get("/projects/{project_id}/plan")
def project_plan(
    request: Request,
    project_id: str,
    year: int = 0,
    week_from: int = 0,
    week_to: int = 0,
):
    selected_holds = request.query_params.getlist("hold")

    project = repo.load_project(project_id)
    result = generate_plan_for_project(project)

    activities = result.activities

    if selected_holds:
        activities = [
            activity
            for activity in activities
            if activity.hold in selected_holds
        ]

    if year:
        activities = [
            activity
            for activity in activities
            if activity.start_dato
            and activity.start_dato.isocalendar().year == year
        ]

    if week_from and week_to:
        if week_from <= week_to:
            activities = [
                activity
                for activity in activities
                if activity.start_dato
                and week_from <= activity.start_dato.isocalendar().week <= week_to
            ]
        else:
            # Periode hen over nytår, fx uge 50 til uge 2
            activities = [
                activity
                for activity in activities
                if activity.start_dato
               and (
                activity.start_dato.isocalendar().week >= week_from
                or activity.start_dato.isocalendar().week <= week_to
            )
        ]

    elif week_from:
        activities = [
            activity
            for activity in activities
            if activity.start_dato
            and activity.start_dato.isocalendar().week >= week_from
        ]

    elif week_to:
        activities = [
            activity
            for activity in activities
            if activity.start_dato
            and activity.start_dato.isocalendar().week <= week_to
        ]

    work_cards = build_work_cards(activities)
    gantt = build_gantt_data(activities)

    return templates.TemplateResponse(
        request,
        "project_plan.html",
        {
            "project": project,
            "result": result,
            "activities": activities,
            "work_cards": work_cards,
            "gantt": gantt,
            "selected_holds": selected_holds,
            "selected_year": year,
            "selected_week_from": week_from,
            "selected_week_to": week_to,
            "teams": get_teams(),
        },
    )

@app.get("/projects/{project_id}/work-cards")
def project_work_cards(request: Request, project_id: str):
    project = repo.load_project(project_id)
    result = generate_plan_for_project(project)
    work_cards = build_work_cards(result.activities)

    return templates.TemplateResponse(
        request,
        "project_work_cards.html",
        {
            "project": project,
            "work_cards": work_cards,
        },
    )