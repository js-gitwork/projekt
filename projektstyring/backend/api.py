from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from projektstyring.backend.project_operations import add_installations
from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.project_writer import save_project


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


def to_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except ValueError:
        return default


@app.get("/")
def index(request: Request):
    projects = repo.list_projects()

    return templates.TemplateResponse(
        request,
        "project_list.html",
        {"projects": projects},
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
        "installations": [],
    }

    if installation_count > 0:
        project = add_installations(
            project,
            installation_count,
        )

    save_project(project)

    return RedirectResponse(url="/", status_code=303)


@app.get("/projects/{project_id}")
def project_detail(request: Request, project_id: str):
    project = repo.load_project(project_id)

    return templates.TemplateResponse(
        request,
        "project_detail.html",
        {"project": project},
    )


@app.post("/projects/{project_id}/installations")
async def save_installations(request: Request, project_id: str):
    project = repo.load_project(project_id)
    form = await request.form()

    installation_count = to_int(form.get("installation_count"), 0)

    installations = []

    for index in range(installation_count):
        installation_id = form.get(f"id_{index}", "").strip()

        if not installation_id:
            continue

        hoveddato = form.get(f"hoveddato_{index}", "").strip()

        installations.append(
            {
                "id": installation_id,
                "hoveddato": hoveddato or None,
                "expected_stik": to_int(form.get(f"expected_stik_{index}")),
                "langhatte": to_int(form.get(f"langhatte_{index}")),
                "korthatte_extra": to_int(
                    form.get(f"korthatte_extra_{index}")
                ),
                "broende": to_int(form.get(f"broende_{index}")),
                "notes": form.get(f"notes_{index}", "").strip(),
            }
        )

    installations.sort(
        key=lambda x: (
            x.get("hoveddato") or "9999-12-31",
            int(x.get("id", 999999))
        )
    )

    project["installations"] = installations
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

    save_project(project)

    return RedirectResponse(
        url=f"/projects/{project_id}",
        status_code=303,
    )
@app.post("/projects/{project_id}/update")
def update_project(
    project_id: str,
    customer: str = Form(""),
    city: str = Form(""),
    start_date: str = Form(""),
    status: str = Form("upcoming"),
):
    project = repo.load_project(project_id)

    project["customer"] = customer.strip()
    project["city"] = city.strip()
    project["start_date"] = start_date
    project["status"] = status

    save_project(project)

    return RedirectResponse(
        url=f"/projects/{project_id}",
        status_code=303,
    )


