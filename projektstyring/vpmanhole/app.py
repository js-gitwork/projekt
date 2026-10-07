from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from projektstyring.backend.auth import (
    authenticate_user,
    hash_password,
    password_is_valid,
    verify_password,
)
from projektstyring.backend.config import require_env
from projektstyring.backend.csrf import (
    get_csrf_token,
    validate_csrf_token,
)
from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.user import User
from projektstyring.vpmanhole.service import VPManholeService


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

app = FastAPI(
    title="VPManhole",
)

vpmanhole_templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates"),
)

auth_templates = Jinja2Templates(
    directory=str(
        PROJECT_ROOT
        / "projektstyring"
        / "frontend"
        / "templates"
    ),
)

auth_templates.env.globals["csrf_token"] = get_csrf_token

service = VPManholeService()


@app.middleware("http")
async def require_login(
    request: Request,
    call_next,
):
    path = request.url.path

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

        request.state.user = user

        return await call_next(request)


app.add_middleware(
    SessionMiddleware,
    secret_key=require_env("SESSION_SECRET"),
    session_cookie="vpmanhole_session",
    max_age=60 * 60 * 12,
    same_site="lax",
    https_only=True,
)


app.mount(
    "/static",
    StaticFiles(
        directory=str(
            PROJECT_ROOT
            / "projektstyring"
            / "frontend"
            / "static"
        )
    ),
    name="static",
)


@app.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        if request.session.get("must_change_password"):
            redirect_url = "/change-password"
        else:
            redirect_url = "/"

        return RedirectResponse(
            url=redirect_url,
            status_code=303,
        )

    return auth_templates.TemplateResponse(
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
            return auth_templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "error": (
                        "Forkert brugernavn eller "
                        "adgangskode."
                    ),
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
    return auth_templates.TemplateResponse(
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
            return auth_templates.TemplateResponse(
                request=request,
                name="change_password.html",
                context={
                    "error": (
                        "Den nuværende adgangskode "
                        "er forkert."
                    ),
                },
                status_code=400,
            )

        if new_password != confirm_password:
            return auth_templates.TemplateResponse(
                request=request,
                name="change_password.html",
                context={
                    "error": (
                        "De to nye adgangskoder "
                        "er ikke ens."
                    ),
                },
                status_code=400,
            )

        valid, message = password_is_valid(
            new_password,
            user.role,
        )

        if not valid:
            return auth_templates.TemplateResponse(
                request=request,
                name="change_password.html",
                context={
                    "error": message,
                },
                status_code=400,
            )

        user.password_hash = hash_password(
            new_password,
        )
        user.must_change_password = False

        session.commit()

        request.session["must_change_password"] = False

    return RedirectResponse(
        url="/",
        status_code=303,
    )


@app.get("/")
def vpmanhole_home(request: Request):
    projects = service.list_open_projects()

    return vpmanhole_templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "projects": projects,
        },
    )


@app.get("/projects/{project_id}/installations")
def vpmanhole_project_installations(
    project_id: str,
):
    normalized_project_id = project_id.strip()

    installations = service.list_project_installations(
        normalized_project_id,
    )

    return {
        "project_id": normalized_project_id,
        "installations": [
            installation
            for installation in installations
            if installation["manholes"]
        ],
    }
