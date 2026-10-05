from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates


router = APIRouter(
    prefix="/vpmanhole",
    tags=["vpmanhole"],
)

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)


@router.get("/")
def vpmanhole_home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )
