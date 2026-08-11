from datetime import date

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from projektstyring.backend.c5_importer import (
    parse_c5_csv,
    parse_c5_technical_asset_import,
)
from projektstyring.backend.project_operations import add_installations
from projektstyring.backend.project_planner import (
    generate_plan_for_active_projects,
    generate_plan_for_project,
)
from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.repositories.team_repository import (
    TeamRepository,
)
from projektstyring.backend.roerbot_service import ask_roerbot
from projektstyring.backend.project_factory import create_project as make_project
from projektstyring.backend.survey_model import default_survey
from projektstyring.backend.project_workflow import (
    complete_survey,
    start_project,
)
from projektstyring.backend.importers.technical_asset_import_executor import (
    TechnicalAssetImportExecutor,
)
from projektstyring.backend.importers.technical_asset_import_service import (
    TechnicalAssetImportService,
)
from projektstyring.backend.task_assignments import (
    TASK_TYPES,
    empty_task_assignments,
    ensure_task_assignments,
)
from projektstyring.backend.snapshot_service import (
    create_snapshot,
    get_latest_snapshot,
)
from fastapi.responses import JSONResponse
from projektstyring.backend.planning_board_service import (
    build_planning_board,
)

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
team_repo = TeamRepository()
technical_asset_import_service = (
    TechnicalAssetImportService(
        TechnicalAssetImportExecutor()
    )
)


def get_teams():
    return team_repo.load_team_map()


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
    except (TypeError, ValueError):
        return default

def calculate_project_status(project):
    status = project.get("status")

    if status in [
        "survey",
        "upcoming",
        "active",
        "completed",
    ]:
        return status

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


def build_work_cards_by_week(activities):
    work_cards = {}

    for activity in activities:
        hold = activity.hold or "Ikke tildelt"

        if not activity.start_dato:
            continue

        iso = activity.start_dato.isocalendar()
        week_key = f"{iso.year}-W{iso.week:02d}"
        week_label = f"Uge {iso.week} / {iso.year}"

        work_cards.setdefault(hold, {})
        work_cards[hold].setdefault(
            week_key,
            {
                "label": week_label,
                "activities": [],
            },
        )

        work_cards[hold][week_key]["activities"].append(activity)

    for hold in work_cards:
        for week_key in work_cards[hold]:
            work_cards[hold][week_key]["activities"] = sorted(
                work_cards[hold][week_key]["activities"],
                key=activity_sort_key,
            )

    return {
        hold: dict(sorted(weeks.items()))
        for hold, weeks in sorted(work_cards.items())
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


def get_project_assigned_team_ids(project):
    team_ids = []

    for assignments in project.get("task_assignments", {}).values():
        for assignment in assignments:
            team = assignment.get("team", "").strip()

            if team and team not in team_ids:
                team_ids.append(team)

    return team_ids


def progress_for_activity(activity_type, progress):
    if activity_type == "hovedledning":
        return progress.get("hovedledning", 0)

    if activity_type == "stikforberedelse":
        return progress.get("stikopmaaling", 0)

    if activity_type == "stik":
        return progress.get("stikaabning", 0)

    if activity_type == "kontrol":
        return progress.get("stikaabning", 0)

    if activity_type == "korthat":
        return 0

    if activity_type == "broend":
        return 0

    return 0


def build_progress_report(project, activities):
    planned = {}

    for activity in activities:
        installation_id = str(activity.installation_id)
        planned.setdefault(installation_id, [])
        planned[installation_id].append(activity)

    report = []
    today = date.today()

    for installation in project.get("installations", []):
        installation_id = str(installation.get("id"))
        progress = installation.get("progress", {})
        planned_activities = planned.get(installation_id, [])

        status = "Ingen plan"
        status_class = "status-muted"

        if planned_activities:
            overdue = False
            in_progress = False
            complete = True

            for activity in planned_activities:
                percent = progress_for_activity(
                    activity.type,
                    progress,
                )

                if percent is None:
                    complete = False

                    if (
                        activity.slut_dato
                        and activity.slut_dato < today
                    ):
                        overdue = True
                    else:
                        in_progress = True

                    continue

                if percent < 100:
                    complete = False

                    if (
                        activity.slut_dato
                        and activity.slut_dato < today
                    ):
                        overdue = True
                    else:
                        in_progress = True

            if complete:
                status = "Færdig"
                status_class = "status-ok"
            elif overdue:
                status = "Bagud"
                status_class = "status-error"
            elif in_progress:
                status = "Planlagt"
                status_class = "status-warning"

        report.append(
            {
                "installation_id": installation_id,
                "active_stik": installation.get("active_stik", 0),
                "planned_activities": planned_activities,
                "progress": progress,
                "status": status,
                "status_class": status_class,
                "notes": installation.get("notes", ""),
            }
        )

    return report


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
    project = make_project(
        project_id=project_id,
        name=name,
        customer=customer,
        city=city,
        start_date=start_date,
        notes="Oprettet via web.",
    )

    if installation_count > 0:
        project = add_installations(
            project,
            installation_count,
        )

    repo.save_project(project)

    return RedirectResponse(
        url=f"/projects/{project_id.strip()}",
        status_code=303,
    )

@app.get("/planning")
def planning_board_page(
    request: Request,
    year: int | None = None,
    week: int | None = None,
    scenario_id: str | None = None,
):
    today = date.today()
    current_iso = today.isocalendar()

    selected_year = year or current_iso.year
    selected_week = week or current_iso.week

    board = build_planning_board(
        year=selected_year,
        week=selected_week,
        scenario_id=scenario_id,
    )

    return templates.TemplateResponse(
        request,
        "planning.html",
        {
            "board": board,
            "selected_year": selected_year,
            "selected_week": selected_week,
            "scenario_id": scenario_id or "",
        },
    )


@app.get("/api/planning-board")
def planning_board_data(
    year: int | None = None,
    week: int | None = None,
    scenario_id: str | None = None,
):
    today = date.today()
    current_iso = today.isocalendar()

    board = build_planning_board(
        year=year or current_iso.year,
        week=week or current_iso.week,
        scenario_id=scenario_id,
    )

    return JSONResponse(
        content=board
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

    repo.save_project(project)

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

@app.post("/projects/{project_id}/start")
def start_project_route(project_id: str):
    project = repo.load_project(project_id)

    baseline = get_latest_snapshot(
        project_id,
        snapshot_type="baseline",
    )

    if baseline is None:
        create_snapshot(
            project_id=project_id,
            project_state=project,
            reason="Projekt startet",
            snapshot_type="baseline",
            phase="baseline",
            metadata={
                "source": "start_project_route",
            },
        )

    project = start_project(project)

    repo.save_project(project)

    return RedirectResponse(
        url=f"/projects/{project_id}",
        status_code=303,
    )

@app.post("/projects/{project_id}/save")
async def save_project_detail(request: Request, project_id: str):
    project = repo.load_project(project_id)
    form = await request.form()

    if project.get("status") == "active":
        create_snapshot(
            project_id=project_id,
            project_state=project,
            reason="Før manuel ændring af aktivt projekt",
            snapshot_type="manual_save",
            phase="before",
            metadata={
                "source": "project_detail_form",
            },
        )

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

    repo.save_project(project)

    return RedirectResponse(
        url=f"/projects/{project_id}",
        status_code=303,
    )

@app.post("/projects/{project_id}/complete-survey")
def complete_project_survey(
    project_id: str,
    installation_count: int = Form(...),
):
    project = repo.load_project(project_id)

    project = complete_survey(
        project,
        installation_count,
    )

    project = ensure_task_assignments(project)
    repo.save_project(project)

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

    repo.save_project(project)

    return RedirectResponse(
        url=f"/projects/{project_id}",
        status_code=303,
    )


@app.get("/projects/{project_id}/plan")
def project_plan(
    request: Request,
    project_id: str,
    year: str = "",
    week_from: str = "",
    week_to: str = "",
):
    selected_holds = request.query_params.getlist("hold")

    year = to_int(
        year,
        date.today().year,
    )
    week_from = to_int(week_from, 0)
    week_to = to_int(week_to, 0)

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

    work_cards = build_work_cards_by_week(activities)
    gantt = build_gantt_data(activities)
    progress_report = build_progress_report(project, activities)

    return templates.TemplateResponse(
        request,
        "project_plan.html",
        {
            "project": project,
            "result": result,
            "activities": activities,
            "work_cards": work_cards,
            "gantt": gantt,
            "progress_report": progress_report,
            "selected_holds": selected_holds,
            "selected_year": year,
            "selected_week_from": week_from,
            "selected_week_to": week_to,
            "teams": {
                team_id: team
                for team_id, team in get_teams().items()
                if team_id in get_project_assigned_team_ids(project)
            },
        },
    )


@app.get("/projects/{project_id}/work-cards")
def project_work_cards(request: Request, project_id: str):
    project = repo.load_project(project_id)
    result = generate_plan_for_project(project)
    work_cards = build_work_cards_by_week(result.activities)

    return templates.TemplateResponse(
        request,
        "project_work_cards.html",
        {
            "project": project,
            "work_cards": work_cards,
        },
    )


@app.get("/projects/{project_id}/c5-import")
def c5_import_form(request: Request, project_id: str):
    project = repo.load_project(project_id)

    return templates.TemplateResponse(
        request,
        "c5_import.html",
        {
            "project": project,
            "csv_text": "",
            "updates": [],
        },
    )

@app.post("/projects/{project_id}/c5-import/preview")
async def c5_import_preview(
    request: Request,
    project_id: str,
):
    project = repo.load_project(project_id)
    form = await request.form()

    csv_text = str(
        form.get("csv_text", "")
    )

    updates = parse_c5_csv(
        csv_text
    )

    updates = [
        update
        for update in updates
        if update.get("project_id") == project_id.upper()
    ]

    return templates.TemplateResponse(
        request,
        "c5_import.html",
        {
            "project": project,
            "csv_text": csv_text,
            "updates": updates,
        },
    )

@app.post("/projects/{project_id}/c5-import/apply")
async def c5_import_apply(
    request: Request,
    project_id: str,
):
    form = await request.form()

    csv_text = str(
        form.get("csv_text", "")
    )

    technical_import = (
        parse_c5_technical_asset_import(
            csv_text=csv_text,
            project_id=project_id,
        )
    )

    technical_asset_import_service.import_assets(
        technical_import
    )

    return RedirectResponse(
        url=f"/projects/{project_id}",
        status_code=303,
    )

@app.post("/assistant/ask")
def roerbot_global_ask(
    question: str = Form(...),
):
    return ask_roerbot(question)
