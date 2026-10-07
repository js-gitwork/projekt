from datetime import date

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from projektstyring.backend.config import require_env
from projektstyring.backend.csrf import (
    csrf_header_is_valid,
    get_csrf_token,
    validate_csrf_token,
)
from projektstyring.backend.auth import (
    authenticate_user,
    hash_password,
    password_is_valid,
    verify_password,
)
from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.user import User
from projektstyring.backend.c5_importer import (
    detect_c5_csv_type,
    parse_c5_csv,
    parse_c5_import,
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
from projektstyring.backend.repositories.conversation_state_repository import (
    create_conversation,
    delete_conversation,
    get_active_conversation,
    list_conversations,
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
from projektstyring.backend.importers.deviation_import import (
    DeviationImport,
)
from projektstyring.backend.importers.deviation_import_service import (
    DeviationImportService,
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
from projektstyring.vpmanhole.router import router as vpmanhole_router

app = FastAPI()


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path

    # Login-siden og statiske filer skal kunne bruges uden login.
    public_path = (
        path == "/login"
        or path.startswith("/static/")
    )

    if public_path:
        return await call_next(request)

    user_id = request.session.get("user_id")

    if user_id is None:
        if request.method == "GET":
            return RedirectResponse(
                url="/login",
                status_code=303,
            )

        return JSONResponse(
            status_code=401,
            content={
                "detail": "Login kræves.",
            },
        )

    with SessionLocal() as session:
        user = session.get(User, user_id)

        if user is None or not user.is_active:
            request.session.clear()

            if request.method == "GET":
                return RedirectResponse(
                    url="/login",
                    status_code=303,
                )

            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Login kræves.",
                },
            )

        role = user.role

        if (
            user.must_change_password
            and path not in {
                "/change-password",
                "/logout",
            }
        ):
            if request.method == "GET":
                return RedirectResponse(
                    url="/change-password",
                    status_code=303,
                )

            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "Adgangskoden skal ændres, "
                        "før systemet kan bruges."
                    ),
                },
            )

        if path == "/logout":
            allowed = True
        elif path.startswith("/vpmanhole"):
            allowed = role in {
                "felt",
                "kontor",
                "admin",
            }
        else:
            allowed = role in {
                "kontor",
                "admin",
            }

        if not allowed:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "Du har ikke adgang til "
                        "denne del af systemet."
                    ),
                },
            )

        request.state.user = user

        response = await call_next(request)

    return response


app.add_middleware(
    SessionMiddleware,
    secret_key=require_env("SESSION_SECRET"),
    session_cookie="projektstyring_session",
    max_age=60 * 60 * 12,
    same_site="lax",
    https_only=True,
)


app.include_router(vpmanhole_router)

app.mount(
    "/static",
    StaticFiles(directory="projektstyring/frontend/static"),
    name="static",
)

templates = Jinja2Templates(
    directory="projektstyring/frontend/templates"
)

templates.env.globals["csrf_token"] = get_csrf_token

repo = ProjectRepository()
team_repo = TeamRepository()
technical_asset_import_service = (
    TechnicalAssetImportService(
        TechnicalAssetImportExecutor()
    )
)

deviation_import_service = (
    DeviationImportService()
)

@app.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        if request.session.get("must_change_password"):
            redirect_url = "/change-password"
        elif request.session.get("role") == "felt":
            redirect_url = "/vpmanhole/"
        else:
            redirect_url = "/"

        return RedirectResponse(
            url=redirect_url,
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": None,
        },
    )


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    validate_csrf_token(
        request,
        csrf_token,
    )
    with SessionLocal() as session:
        user = authenticate_user(
            session,
            username,
            password,
        )

        if user is None:
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "error": "Forkert brugernavn eller adgangskode.",
                },
                status_code=401,
            )

        request.session.clear()

        request.session["user_id"] = user.id
        request.session["username"] = user.username
        request.session["display_name"] = user.display_name
        request.session["role"] = user.role
        request.session["must_change_password"] = (
            user.must_change_password
        )

        if user.must_change_password:
            redirect_url = "/change-password"
        elif user.role == "felt":
            redirect_url = "/vpmanhole/"
        else:
            redirect_url = "/"

    return RedirectResponse(
        url=redirect_url,
        status_code=303,
    )

@app.post("/logout")
def logout(
    request: Request,
    csrf_token: str = Form(...),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    request.session.clear()

    return RedirectResponse(
        url="/login",
        status_code=303,
    )

@app.get("/change-password")
def change_password_page(request: Request):
    user_id = request.session.get("user_id")

    if user_id is None:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="change_password.html",
        context={
            "error": None,
        },
    )


@app.post("/change-password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(...),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

    user_id = request.session.get("user_id")

    if user_id is None:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    with SessionLocal() as session:
        user = session.get(User, user_id)

        if user is None or not user.is_active:
            request.session.clear()

            return RedirectResponse(
                url="/login",
                status_code=303,
            )

        if not verify_password(
            current_password,
            user.password_hash,
        ):
            return templates.TemplateResponse(
                request=request,
                name="change_password.html",
                context={
                    "error": "Den nuværende adgangskode er forkert.",
                },
                status_code=400,
            )

        if new_password != confirm_password:
            return templates.TemplateResponse(
                request=request,
                name="change_password.html",
                context={
                    "error": "De to nye adgangskoder er ikke ens.",
                },
                status_code=400,
            )

        valid, message = password_is_valid(
            new_password,
            user.role,
        )

        if not valid:
            return templates.TemplateResponse(
                request=request,
                name="change_password.html",
                context={
                    "error": message,
                },
                status_code=400,
            )

        user.password_hash = hash_password(
            new_password
        )
        user.must_change_password = False

        session.commit()

        request.session["must_change_password"] = False

        role = user.role

    if role == "felt":
        return RedirectResponse(
            url="/vpmanhole/",
            status_code=303,
        )

    return RedirectResponse(
        url="/",
        status_code=303,
    )

def get_teams():
    return team_repo.load_team_map()

def to_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default

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
    request: Request,
    project_id: str = Form(...),
    name: str = Form(...),
    customer: str = Form(""),
    city: str = Form(""),
    start_date: str = Form(...),
    installation_count: int = Form(0),
    csrf_token: str = Form(...),
):
    validate_csrf_token(
        request,
        csrf_token,
    )
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

    project = ensure_task_assignments(project)

    project["installations"] = sorted(
        project.get("installations", []),
        key=installation_sort_key,
    )

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
def start_project_route(
    request: Request,
    project_id: str,
    csrf_token: str = Form(...),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

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

    validate_csrf_token(
        request,
        str(form.get("csrf_token", "")),
    )

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
    request: Request,
    project_id: str,
    installation_count: int = Form(...),
    csrf_token: str = Form(...),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

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
    request: Request,
    project_id: str,
    installation_count: int = Form(...),
    csrf_token: str = Form(...),
):
    validate_csrf_token(
        request,
        csrf_token,
    )

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

def build_c5_import_report(preview_result):
    """
    Bygger en deterministisk kontrolrapport til Rørbot
    ud fra importmotorens faktiske preview-resultat.

    Funktionen foretager ingen selvstændig importkontrol
    og ændrer ingen data.
    """

    conflicts = list(
        preview_result.conflicts
    )

    blocking = [
        conflict
        for conflict in conflicts
        if conflict.blocks_import
    ]

    non_blocking = [
        conflict
        for conflict in conflicts
        if not conflict.blocks_import
    ]

    if blocking:
        status = "blocked"

        summary = (
            f"Jeg har fundet {len(conflicts)} "
            "konflikt(er), hvoraf "
            f"{len(blocking)} blokerer importen. "
            "Importen kan ikke godkendes, før "
            "de blokerende konflikter er løst."
        )

    elif non_blocking:
        status = "warning"

        summary = (
            f"Jeg har fundet {len(non_blocking)} "
            "ikke-blokerende konflikt(er). "
            "Importen kan gennemføres, men de "
            "konfliktramte oplysninger håndteres "
            "efter importmotorens sikkerhedsregler. "
            "Se detaljerne nedenfor."
        )

    else:
        status = "ok"

        summary = (
            "Jeg har kontrolleret forhåndsvisningen. "
            "Alt er i orden – ingen konflikter fundet. "
            "Importen er klar til godkendelse."
        )

    work_entries = [
        action.key
        for action in preview_result.actions
        if (
            action.entity_type == "manhole_work"
            and action.action == "create"
        )
    ]

    return {
        "status": status,
        "summary": summary,
        "conflicts": conflicts,
        "blocking_count": len(blocking),
        "non_blocking_count": len(non_blocking),
        "can_import": not blocking,
        "created": preview_result.created,
        "updated": preview_result.updated,
        "unchanged": preview_result.unchanged,
        "work_entries_created": (
            preview_result.work_entries_created
        ),
        "work_entries": work_entries,
    }

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

    validate_csrf_token(
        request,
        str(form.get("csrf_token", "")),
    )

    csv_text = str(
        form.get("csv_text", "")
    )

    import_type = detect_c5_csv_type(
        csv_text
    )

    import_data = parse_c5_import(
        csv_text=csv_text,
        project_id=project_id,
    )

    if isinstance(
        import_data,
        DeviationImport,
    ):
        updates = []

        preview_result = (
            deviation_import_service.preview(
                import_data
            )
        )

    else:
        # Den eksisterende detaljerede
        # C5-preview for tekniske data.
        updates = parse_c5_csv(
            csv_text
        )

        updates = [
            update
            for update in updates
            if (
                update.get("project_id")
                == project_id.upper()
            )
        ]

        preview_result = (
            technical_asset_import_service.preview(
                import_data
            )
        )

    roerbot_import_report = build_c5_import_report(
        preview_result
    )

    return templates.TemplateResponse(
        request,
        "c5_import.html",
        {
            "project": project,
            "csv_text": csv_text,
            "import_type": import_type,
            "updates": updates,
            "preview_result": preview_result,
            "roerbot_import_report": roerbot_import_report,
        },
    )

@app.post("/projects/{project_id}/c5-import/apply")
async def c5_import_apply(
    request: Request,
    project_id: str,
):
    form = await request.form()

    validate_csrf_token(
        request,
        str(form.get("csrf_token", "")),
    )

    csv_text = str(
        form.get("csv_text", "")
    )

    import_data = parse_c5_import(
        csv_text=csv_text,
        project_id=project_id,
    )

    if isinstance(
        import_data,
        DeviationImport,
    ):
        deviation_import_service.import_deviations(
            import_data
        )

    else:
        technical_asset_import_service.import_assets(
            import_data
        )

    return RedirectResponse(
        url=f"/projects/{project_id}",
        status_code=303,
    )

def roerbot_user_key(request: Request) -> str:
    return f"user:{request.state.user.id}"


@app.get("/assistant/conversations")
def roerbot_list_conversations(
    request: Request,
):
    user_key = roerbot_user_key(request)

    conversations = list_conversations(
        user_key=user_key,
    )

    return {
        "conversations": [
            {
                "conversation_key": (
                    conversation.conversation_key
                ),
                "title": conversation.title,
                "kind": conversation.kind,
                "updated_at": (
                    conversation.updated_at.isoformat()
                ),
            }
            for conversation in conversations
        ]
    }


@app.post("/assistant/conversations")
def roerbot_create_conversation(
    request: Request,
):

    if not csrf_header_is_valid(request):
        raise HTTPException(
            status_code=403,
            detail="Ugyldigt eller manglende CSRF-token.",
        )

    user_key = roerbot_user_key(request)

    conversation = create_conversation(
        user_key=user_key,
        kind="normal",
    )

    return {
        "conversation_key": conversation.conversation_key,
        "title": conversation.title,
        "kind": conversation.kind,
    }


@app.post("/assistant/conversations/close")
def roerbot_close_conversation(
    request: Request,
    conversation_key: str = Form(...),
):

    if not csrf_header_is_valid(request):
        raise HTTPException(
            status_code=403,
            detail="Ugyldigt eller manglende CSRF-token.",
        )

    deleted = delete_conversation(
        user_key=roerbot_user_key(request),
        conversation_key=conversation_key,
    )

    if not deleted:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Samtalen findes ikke.",
            },
        )

    return {
        "ok": True,
    }


@app.post("/assistant/ask")
def roerbot_global_ask(
    request: Request,
    question: str = Form(...),
    conversation_key: str = Form(...),
):

    if not csrf_header_is_valid(request):
        raise HTTPException(
            status_code=403,
            detail="Ugyldigt eller manglende CSRF-token.",
        )

    user = request.state.user
    user_key = f"user:{user.id}"

    result = ask_roerbot(
        question,
        user_key=user_key,
        conversation_key=conversation_key,
        actor_name=(
            user.display_name
            or user.username
        ),
    )

    conversation = get_active_conversation(
        user_key=user_key,
        conversation_key=conversation_key,
    )

    if conversation is not None:
        result["conversation_title"] = conversation.title

    return result