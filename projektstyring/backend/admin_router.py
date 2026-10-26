from __future__ import annotations

import re
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
from projektstyring.backend.db_models.vpmanhole_notification import (
    VPManholeNotificationRecipient,
    VPManholeNotificationSettings,
)

router = APIRouter(prefix="/admin", tags=["Administration"])

ROLES = {"felt", "kontor", "admin"}

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\."
    r"[A-Za-z]{2,63}$"
)


def normalize_email(email: str, role: str) -> str | None:
    email = email.strip().lower()

    if not email:
        if role in {"kontor", "admin"}:
            raise HTTPException(
                status_code=400,
                detail="Kontorbrugere og administratorer skal have en e-mailadresse.",
            )
        return None

    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(
            status_code=400,
            detail="Ugyldig e-mailadresse.",
        )

    return email

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

        notification_settings = session.get(
            VPManholeNotificationSettings, 1
        )

        notification_enabled = (
            notification_settings.enabled
            if notification_settings
            else False
        )

        include_site_manager = (
            notification_settings.include_site_manager
            if notification_settings
            else False
        )

        recipient_ids = set(
            session.scalars(
                select(VPManholeNotificationRecipient.user_id)
            ).all()
        )

        eligible_recipients = [
            user
            for user in users
            if user.is_active
            and user.role in {"kontor", "admin"}
            and user.email
        ]

        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={
                "users": users,
                "notification_enabled": notification_enabled,
                "include_site_manager": include_site_manager,
                "notification_recipients": eligible_recipients,
                "notification_recipient_ids": recipient_ids,
            },
        )


@router.post("/vpmanhole/notifications")
def update_vpmanhole_notifications(
    request: Request,
    csrf_token: str = Form(...),
    recipient_ids: list[int] = Form(default=[]),
    include_site_manager: bool = Form(False),
    enabled: bool = Form(False),
):
    require_admin(request)
    validate_csrf_token(request, csrf_token)

    with SessionLocal() as session:
        eligible_users = session.scalars(
            select(User).where(
                User.is_active.is_(True),
                User.role.in_(("kontor", "admin")),
                User.email.is_not(None),
            )
        ).all()

        eligible_ids = {
            user.id
            for user in eligible_users
            if user.email and user.email.strip()
        }

        requested_ids = set(recipient_ids)

        if not requested_ids.issubset(eligible_ids):
            raise HTTPException(
                status_code=400,
                detail="En eller flere valgte mailmodtagere er ugyldige.",
            )

        settings = session.get(
            VPManholeNotificationSettings, 1
        )

        if settings is None:
            settings = VPManholeNotificationSettings(id=1)
            session.add(settings)

        settings.enabled = enabled
        settings.include_site_manager = include_site_manager

        existing_recipients = session.scalars(
            select(VPManholeNotificationRecipient)
        ).all()

        existing_by_user_id = {
            recipient.user_id: recipient
            for recipient in existing_recipients
        }

        for user_id, recipient in existing_by_user_id.items():
            if user_id not in requested_ids:
                session.delete(recipient)

        for user_id in requested_ids:
            if user_id not in existing_by_user_id:
                session.add(
                    VPManholeNotificationRecipient(
                        user_id=user_id
                    )
                )

        session.commit()

    return redirect_admin()




@router.post("/users/create")
def create_user(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    email: str = Form(""),
    csrf_token: str = Form(...),
):
    require_admin(request)
    validate_csrf_token(request, csrf_token)

    username = username.strip().lower()
    display_name = display_name.strip()

    if not username or not display_name or role not in ROLES:
        raise HTTPException(400, "Ugyldige brugeroplysninger.")

    normalized_email = normalize_email(email, role)

    valid, message = password_is_valid(password, role)

    if not valid:
        raise HTTPException(400, message)

    with SessionLocal() as session:
        existing = session.scalar(
            select(User).where(User.username == username)
        )

        if normalized_email:
            existing_email = session.scalar(
                select(User).where(User.email == normalized_email)
            )
            if existing_email:
                raise HTTPException(
                    400,
                    "E-mailadressen er allerede registreret på en anden bruger.",
                )

        if existing:
            raise HTTPException(400, "Brugernavnet findes allerede.")

        session.add(
            User(
                username=username,
                display_name=display_name,
                email=normalized_email,
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
    email: str = Form(""),
    csrf_token: str = Form(...),
):
    require_admin(request)
    validate_csrf_token(request, csrf_token)

    if role not in ROLES or not display_name.strip():
        raise HTTPException(400, "Ugyldige oplysninger.")

    normalized_email = normalize_email(email, role)

    with SessionLocal() as session:
        user = session.get(User, user_id)

        if user is None:
            raise HTTPException(404, "Brugeren findes ikke.")

        if normalized_email:
            existing_email = session.scalar(
                select(User).where(
                    User.email == normalized_email,
                    User.id != user_id,
                )
            )

            if existing_email:
                raise HTTPException(
                    400,
                    "E-mailadressen er allerede registreret på en anden bruger.",
                )

        if user.role == "admin" and role != "admin":
            ensure_other_admin_exists(session, user)

        user.display_name = display_name.strip()
        user.email = normalized_email

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
