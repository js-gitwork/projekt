from __future__ import annotations

import secrets

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from projektstyring.backend.auth import (
    hash_password,
    password_is_valid,
)
from projektstyring.backend.csrf import validate_csrf_token
from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.user import User

router = APIRouter(prefix="/admin", tags=["Administration"])

ROLES = {"felt", "kontor", "admin"}


def require_admin(request: Request) -> User:
    user = getattr(request.state, "user", None)

    if user is None or user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Kun administratorer har adgang.",
        )

    return user


def redirect_admin() -> RedirectResponse:
    return RedirectResponse(
        url="/admin",
        status_code=303,
    )


def ensure_other_admin_exists(session, target: User) -> None:
    """
    Forhindrer at den sidste aktive administrator
    deaktiveres eller mister administratorrollen.
    """
    if not target.is_active or target.role != "admin":
        return

    active_admins = session.scalar(
        select(func.count(User.id)).where(
            User.role == "admin",
            User.is_active.is_(True),
        )
    )

    if active_admins <= 1:
        raise HTTPException(
            status_code=400,
            detail="Den sidste aktive administrator kan ikke fjernes.",
        )


@router.get("")
def admin_page(request: Request):
    require_admin(request)

    from projektstyring.backend.api import templates

    with SessionLocal() as session:
        users = session.scalars(
            select(User).order_by(User.username)
        ).all()

        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={"users": users},
        )


@router.post("/users/create")
def create_user(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    require_admin(request)
    validate_csrf_token(request, csrf_token)

    username = username.strip().lower()
    display_name = display_name.strip()

    if not username or not display_name or role not in ROLES:
        raise HTTPException(400, "Ugyldige brugeroplysninger.")

    valid, message = password_is_valid(password, role)

    if not valid:
        raise HTTPException(400, message)

    with SessionLocal() as session:
        existing = session.scalar(
            select(User).where(User.username == username)
        )

        if existing:
            raise HTTPException(400, "Brugernavnet findes allerede.")

        session.add(
            User(
                username=username,
                display_name=display_name,
                role=role,
                password_hash=hash_password(password),
                is_active=True,
                must_change_password=True,
            )
        )

        session.commit()

    return redirect_admin()


@router.post("/users/{user_id}/update")
def update_user(
    user_id: int,
    request: Request,
    display_name: str = Form(...),
    role: str = Form(...),
    csrf_token: str = Form(...),
):
    require_admin(request)
    validate_csrf_token(request, csrf_token)

    if role not in ROLES or not display_name.strip():
        raise HTTPException(400, "Ugyldige oplysninger.")

    with SessionLocal() as session:
        user = session.get(User, user_id)

        if user is None:
            raise HTTPException(404, "Brugeren findes ikke.")

        if user.role == "admin" and role != "admin":
            ensure_other_admin_exists(session, user)

        user.display_name = display_name.strip()
        if user.role != role:
            user.session_version += 1

        user.role = role

        session.commit()

    return redirect_admin()


@router.post("/users/{user_id}/toggle")
def toggle_user(
    user_id: int,
    request: Request,
    csrf_token: str = Form(...),
):
    require_admin(request)
    validate_csrf_token(request, csrf_token)

    with SessionLocal() as session:
        user = session.get(User, user_id)

        if user is None:
            raise HTTPException(404, "Brugeren findes ikke.")

        if user.is_active:
            ensure_other_admin_exists(session, user)

        user.is_active = not user.is_active
        user.session_version += 1

        session.commit()

    return redirect_admin()


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    request: Request,
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    require_admin(request)
    validate_csrf_token(request, csrf_token)

    with SessionLocal() as session:
        user = session.get(User, user_id)

        if user is None:
            raise HTTPException(404, "Brugeren findes ikke.")

        valid, message = password_is_valid(password, user.role)

        if not valid:
            raise HTTPException(400, message)

        user.password_hash = hash_password(password)
        user.must_change_password = True
        user.session_version += 1

        session.commit()

    return redirect_admin()
