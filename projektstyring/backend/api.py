from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from projektstyring.backend.project_repository import ProjectRepository


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


@app.get("/")
def index(request: Request):
    projects = repo.list_projects()

    return templates.TemplateResponse(
        request,
        "project_list.html",
        {
            "projects": projects,
        },
    )
