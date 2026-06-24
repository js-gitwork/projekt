import sys
sys.path.append("/home/media/projekter")
from core.ai_assistent import ask_mistral

from datetime import date
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from projektstyring.backend.c5_importer import (
    parse_c5_csv,
    apply_c5_updates_to_project,
)
from projektstyring.backend.project_planner import (
    generate_plan_for_project,
    generate_plan_for_active_projects,
)
from projektstyring.backend.project_operations import add_installations
from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.project_writer import save_project
from projektstyring.backend.team_loader import load_teams
from core.ai_assistent import ask_mistral
import json
from pathlib import Path

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

ROERBOT_BEGREBER_FILE = Path("projektstyring/data/roerbot_begreber.json")


def load_roerbot_begreber():
    if not ROERBOT_BEGREBER_FILE.exists():
        return {}

    with ROERBOT_BEGREBER_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)

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

@app.get("/projects/{project_id}/assistant", response_class=HTMLResponse)
def project_assistant_page(request: Request, project_id: str):
    project = repository.load_project(project_id)

    return templates.TemplateResponse(
        "assistant.html",
        {
            "request": request,
            "project": project,
            "answer": None,
            "question": "",
        },
    )
@app.post("/assistant/ask")
def roerbot_ask(question: str = Form(...)):
    print("Roerbot spørgsmål:", question)

    prompt = f"""
Du er Roerbot, projektassistent.

Spørgsmål:
{question}
"""

    answer = ask_mistral(
        prompt,
        model="mistral-small-latest"
    )

    return {"answer": answer}


@app.post("/projects/{project_id}/assistant", response_class=HTMLResponse)
def project_assistant_ask(
    request: Request,
    project_id: str,
    question: str = Form(...),
):
    project = repository.load_project(project_id)

    prompt = f"""
Du er projektassistent.

Projekt:
{project.id} - {project.name}

Spørgsmål:
{question}
"""

    answer = ask_mistral(
        prompt,
        model="mistral-small-latest"
    )

    return templates.TemplateResponse(
        "assistant.html",
        {
            "request": request,
            "project": project,
            "answer": answer,
            "question": question,
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


def get_project_assigned_team_ids(project):
    team_ids = []

    for assignments in project.get("task_assignments", {}).values():
        for assignment in assignments:
            team = assignment.get("team", "").strip()

            if team and team not in team_ids:
                team_ids.append(team)

    return team_ids


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

                if percent < 100:
                    complete = False

                    if activity.slut_dato and activity.slut_dato < today:
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
async def c5_import_preview(request: Request, project_id: str):
    project = repo.load_project(project_id)
    form = await request.form()

    csv_text = form.get("csv_text", "")
    updates = parse_c5_csv(csv_text)

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
async def c5_import_apply(request: Request, project_id: str):
    project = repo.load_project(project_id)
    form = await request.form()

    csv_text = form.get("csv_text", "")
    updates = parse_c5_csv(csv_text)

    project = apply_c5_updates_to_project(
        project,
        updates,
    )

    save_project(project)

    return RedirectResponse(
        url=f"/projects/{project_id}",
        status_code=303,
    )

def detect_team_capacity_change(question: str):
    text = question.lower()

    if "stik2" in text or "stik 2" in text:
        team = "stik2"
    else:
        team = None

    if "6" in text and ("langhat" in text or "stik" in text):
        new_capacity = 6
    else:
        new_capacity = None

    if team and new_capacity:
        return {
            "intent": "update_team_capacity",
            "team": team,
            "field": "langhatte_per_day",
            "new_value": new_capacity,
            "requires_confirmation": True,
        }

    return None

@app.post("/projects/{project_id}/assistant/ask")
def roerbot_project_ask(
    project_id: str,
    question: str = Form(...),
):
    def as_int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    project = repo.load_project(project_id)

    roerbot_begreber = load_roerbot_begreber()

    print("ROERBOT QUESTION:", question)

    change_proposal = detect_team_capacity_change(question)
    print("CHANGE PROPOSAL:", change_proposal)

        if change_proposal:
            answer = f"""
    Jeg har forstået det som et ændringsforslag:

    Hold: {change_proposal["team"]}
    Ændring: kapacitet sættes til {change_proposal["new_value"]} langhatte pr. dag.

    Jeg har ikke ændret noget endnu.
    Dette kræver godkendelse, før data må gemmes.
    """

        return {
            "answer": answer,
            "proposal": change_proposal,
        }

    task_assignments = project.get("task_assignments", [])
    installations = project.get("installations", [])

    installation_summary = [
        {
            "id": installation.get("id"),
            "active": installation.get("active"),
            "expected_stik": as_int(installation.get("expected_stik")),
            "active_stik": as_int(installation.get("active_stik")),
            "langhatte": as_int(installation.get("langhatte")),
            "korthatte_extra": as_int(installation.get("korthatte_extra")),
            "broende": as_int(installation.get("broende")),
            "main_date": installation.get("main_date"),
            "notes": installation.get("notes"),
        }
        for installation in installations
    ]

    prompt = f"""
Du er Roerbot, projektassistent for strømpeforingsprojekter.

Du må kun svare ud fra de data, du får her.
Du må ikke gætte.
Hvis data ikke findes i projektdataene, skal du sige det.

Svarregler:
- Svar kort og præcist.
- Svar kun på det brugeren spørger om.
- Hvis brugeren spørger "hvilke installationer", så svar kun med installationsnumre.
- Hvis brugeren spørger "hvor mange", så svar med tallet først.
- Vis ikke noter, adresser, strækninger eller bemærkninger medmindre brugeren specifikt beder om dem.
- Hold svar under 5 linjer hvis muligt.
- Vær faktuel frem for hjælpsom.
- Forklar ikke hvordan du kom frem til svaret medmindre brugeren spørger.

Virksomhedens begreber:
{json.dumps(roerbot_begreber, indent=2, ensure_ascii=False)}

Projekt:
ID: {project.get("id")}
Navn: {project.get("name")}
Tilknyttede hold:
{json.dumps(assigned_teams, indent=2, ensure_ascii=False)}

Antal tilknyttede hold:
{len(assigned_teams)}

Holdtildelinger:
{json.dumps(task_assignments, indent=2, ensure_ascii=False)}

Installationer:
{json.dumps(installation_summary, indent=2, ensure_ascii=False)}

Spørgsmål:
{question}
"""

    answer = ask_mistral(
        prompt,
        model="mistral-small-latest"
    )

    return {"answer": answer}