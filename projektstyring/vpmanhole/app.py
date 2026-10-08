from __future__ import annotations

from pathlib import Path

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
)
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
from sqlalchemy import select

from projektstyring.backend.db_models import (
    Installation,
    Manhole,
    Stretch,
    VPManholeDelivery,
    VPManholePhoto,
)
from projektstyring.vpmanhole.service import VPManholeService
from projektstyring.vpmanhole.photo_service import (
    MAX_UPLOAD_BYTES,
    PhotoServiceError,
    VPManholePhotoService,
)


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

app = FastAPI(
    title="VPManhole",
)

vpmanhole_templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates"),
)

vpmanhole_templates.env.globals["csrf_token"] = get_csrf_token

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
photo_service = VPManholePhotoService()


@app.middleware("http")
async def require_login(
    request: Request,
    call_next,
):
    path = request.url.path

    public_path = (
        path == "/login"
        or path.startswith("/static/")
        or path.startswith("/vpmanhole-static/")
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

app.mount(
    "/vpmanhole-static",
    StaticFiles(
        directory=str(BASE_DIR / "static")
    ),
    name="vpmanhole-static",
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

    return vpmanhole_templates.TemplateResponse(
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
            return vpmanhole_templates.TemplateResponse(
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
    return vpmanhole_templates.TemplateResponse(
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
            return vpmanhole_templates.TemplateResponse(
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
            return vpmanhole_templates.TemplateResponse(
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
            return vpmanhole_templates.TemplateResponse(
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
    user = request.state.user

    if user.role in {"kontor", "admin"}:
        template_name = "transfer.html"
    else:
        template_name = "index.html"

    return vpmanhole_templates.TemplateResponse(
        request=request,
        name=template_name,
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

@app.post("/projects/{project_id}/manholes/{manhole_id}/photos")
async def upload_manhole_photo(
    request: Request,
    project_id: str,
    manhole_id: int,
    installation_id: int = Form(...),
    photo_type: str = Form(...),
    sequence: int = Form(1),
    csrf_token: str = Form(...),
    image: UploadFile = File(...),
):
    """
    Modtag og gem et brøndfoto fra tabletvisningen.

    Kræver:
    - Gyldigt login
    - Feltbruger
    - Gyldigt CSRF-token
    - Gyldigt projekt, installation og brønd
    - Understøttet billedtype
    """

    user = request.state.user

    if user.role != "felt":
        raise HTTPException(
            status_code=403,
            detail="Du har ikke adgang til at uploade billeder.",
        )

    validate_csrf_token(request, csrf_token)

    if photo_type not in {
        "before",
        "during",
        "after",
        "cover",
    }:
        raise HTTPException(
            status_code=400,
            detail="Ukendt billedtype.",
        )

    if sequence < 1:
        raise HTTPException(
            status_code=400,
            detail="Ugyldigt billednummer.",
        )

    if photo_type != "during" and sequence != 1:
        raise HTTPException(
            status_code=400,
            detail="Denne billedtype kan kun have ét billede.",
        )

    if image.content_type not in {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    }:
        raise HTTPException(
            status_code=400,
            detail="Billedformatet understøttes ikke.",
        )

    try:
        image_bytes = await image.read(
            MAX_UPLOAD_BYTES + 1
        )
    finally:
        await image.close()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Billedfilen er tom.",
        )

    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Billedet må højst fylde 20 MB.",
        )

    try:
        with SessionLocal() as session:
            photo = photo_service.save_photo(
                session,
                project_id=project_id.strip(),
                installation_id=installation_id,
                manhole_id=manhole_id,
                photo_type=photo_type,
                image_bytes=image_bytes,
                user_id=user.id,
                sequence=sequence,
            )

            result = {
                "success": True,
                "photo_id": photo.id,
                "photo_type": photo.photo_type,
                "sequence": photo.sequence,
                "message": "Billedet er gemt.",
            }

    except PhotoServiceError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return result

@app.get("/projects/{project_id}/installations/{installation_id}/photo-status")
def get_installation_photo_status(
    request: Request,
    project_id: str,
    installation_id: int,
):
    """
    Returnerer dokumentationsstatus for alle brønde
    tilknyttet en installation.

    Kun før, efter og dæksel tæller som obligatoriske.
    """

    with SessionLocal() as session:
        installation = session.get(Installation, installation_id)

        if (
            installation is None
            or installation.project_id != project_id
            or not installation.active
        ):
            raise HTTPException(
                status_code=404,
                detail="Installationen blev ikke fundet.",
            )

        manhole_ids = set(
            session.scalars(
                select(Stretch.bottom_manhole_id).where(
                    Stretch.installation_id == installation_id,
                    Stretch.bottom_manhole_id.is_not(None),
                )
            ).all()
        )

        manhole_ids.update(
            session.scalars(
                select(Stretch.top_manhole_id).where(
                    Stretch.installation_id == installation_id,
                    Stretch.top_manhole_id.is_not(None),
                )
            ).all()
        )

        if not manhole_ids:
            return {"manholes": {}}

        rows = session.execute(
            select(
                VPManholeDelivery.manhole_id,
                VPManholePhoto.photo_type,
            )
            .join(
                VPManholePhoto,
                VPManholePhoto.delivery_id == VPManholeDelivery.id,
            )
            .where(
                VPManholeDelivery.manhole_id.in_(manhole_ids),
                VPManholePhoto.photo_type.in_(
                    ["before", "after", "cover"]
                ),
            )
        ).all()

        completed_types = {
            manhole_id: set()
            for manhole_id in manhole_ids
        }

        for manhole_id, photo_type in rows:
            completed_types[manhole_id].add(photo_type)

        return {
            "manholes": {
                str(manhole_id): {
                    "completed": len(completed_types[manhole_id]),
                    "required": 3,
                    "complete": len(completed_types[manhole_id]) == 3,
                }
                for manhole_id in manhole_ids
            }
        }

@app.get("/projects/{project_id}/manholes/{manhole_id}/photos")
def list_manhole_photos(
    request: Request,
    project_id: str,
    manhole_id: int,
    installation_id: int,
):
    """
    Hent listen over gemte billeder for en brønd.
    """

    with SessionLocal() as session:
        manhole = session.get(Manhole, manhole_id)
        installation = session.get(
            Installation,
            installation_id,
        )

        if (
            manhole is None
            or installation is None
            or manhole.project_id != project_id
            or installation.project_id != project_id
            or not manhole.active
            or not installation.active
        ):
            raise HTTPException(
                status_code=404,
                detail="Brønd eller installation blev ikke fundet.",
            )

        linked = session.scalar(
            select(Stretch.id)
            .where(
                Stretch.installation_id == installation_id,
                (
                    (Stretch.bottom_manhole_id == manhole_id)
                    | (Stretch.top_manhole_id == manhole_id)
                ),
            )
            .limit(1)
        )

        if linked is None:
            raise HTTPException(
                status_code=404,
                detail="Brønden hører ikke til installationen.",
            )

        delivery = session.scalar(
            select(VPManholeDelivery).where(
                VPManholeDelivery.manhole_id == manhole_id
            )
        )

        if delivery is None:
            return {"photos": []}

        photos = session.scalars(
            select(VPManholePhoto)
            .where(
                VPManholePhoto.delivery_id == delivery.id
            )
            .order_by(
                VPManholePhoto.photo_type,
                VPManholePhoto.sequence,
            )
        ).all()

        return {
            "photos": [
                {
                    "id": photo.id,
                    "photo_type": photo.photo_type,
                    "sequence": photo.sequence,
                    "url": (
                        f"/projects/{project_id}"
                        f"/manholes/{manhole_id}"
                        f"/photos/{photo.id}"
                        f"?installation_id={installation_id}"
                    ),
                }
                for photo in photos
            ]
        }


@app.get("/projects/{project_id}/manholes/{manhole_id}/photos/{photo_id}")
def get_manhole_photo(
    request: Request,
    project_id: str,
    manhole_id: int,
    photo_id: int,
    installation_id: int,
):
    """
    Hent et gemt brøndfoto.

    Filen findes via databasen, aldrig via en
    filsti leveret af brugeren.
    """

    with SessionLocal() as session:
        manhole = session.get(Manhole, manhole_id)
        installation = session.get(
            Installation,
            installation_id,
        )

        if (
            manhole is None
            or installation is None
            or manhole.project_id != project_id
            or installation.project_id != project_id
            or not manhole.active
            or not installation.active
        ):
            raise HTTPException(
                status_code=404,
                detail="Brønd eller installation blev ikke fundet.",
            )

        linked = session.scalar(
            select(Stretch.id)
            .where(
                Stretch.installation_id == installation_id,
                (
                    (Stretch.bottom_manhole_id == manhole_id)
                    | (Stretch.top_manhole_id == manhole_id)
                ),
            )
            .limit(1)
        )

        if linked is None:
            raise HTTPException(
                status_code=404,
                detail="Brønden hører ikke til installationen.",
            )

        photo = session.scalar(
            select(VPManholePhoto)
            .join(
                VPManholeDelivery,
                VPManholePhoto.delivery_id == VPManholeDelivery.id,
            )
            .where(
                VPManholePhoto.id == photo_id,
                VPManholeDelivery.manhole_id == manhole_id,
            )
        )

        if photo is None:
            raise HTTPException(
                status_code=404,
                detail="Billedet blev ikke fundet.",
            )

        storage_root = photo_service.storage_root

        image_path = (
            storage_root / photo.relative_path
        ).resolve()

        if not image_path.is_relative_to(storage_root):
            raise HTTPException(
                status_code=404,
                detail="Ugyldig billedsti.",
            )

        if not image_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Billedfilen findes ikke.",
            )

        return FileResponse(
            path=image_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )