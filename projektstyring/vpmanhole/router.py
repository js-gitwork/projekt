from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from projektstyring.vpmanhole.service import VPManholeService


router = APIRouter(
    prefix="/vpmanhole",
    tags=["vpmanhole"],
)

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

service = VPManholeService()


@router.get("/")
def vpmanhole_home(request: Request):
    projects = service.list_open_projects()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "projects": projects,
        },
    )

@router.get("/projects/{project_id}/installations")
def vpmanhole_project_installations(project_id: str):
    installations = service.list_project_installations(
        project_id.strip()
    )

    return {
        "project_id": project_id.strip(),
        "installations": [
            installation
            for installation in installations
            if installation["manholes"]
        ],
    }