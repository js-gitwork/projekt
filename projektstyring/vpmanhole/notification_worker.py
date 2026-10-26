
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.project import Project
from projektstyring.backend.db_models.vpmanhole import (
    VPManholeDelivery,
    VPManholePhoto,
)
from projektstyring.backend.repositories.database_project_repository import (
    DatabaseProjectRepository,
)
from projektstyring.backend.db_models.user import User
from projektstyring.backend.db_models.vpmanhole_notification import (
    VPManholeNotificationEvent,
    VPManholeNotificationRecipient,
    VPManholeNotificationSettings,
)
from projektstyring.vpmanhole.graph_mail import send_mail
from projektstyring.vpmanhole.notification_service import (
    notification_service,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_recipients(
    session,
    project: Project,
    settings: VPManholeNotificationSettings,
) -> list[str]:
    rows = session.execute(
        select(User)
        .join(
            VPManholeNotificationRecipient,
            VPManholeNotificationRecipient.user_id == User.id,
        )
        .where(
            User.is_active.is_(True),
            User.role.in_(("kontor", "admin")),
            User.email.is_not(None),
        )
    ).scalars().all()

    emails = {
        user.email.strip().lower()
        for user in rows
        if user.email and user.email.strip()
    }

    if (
        settings.include_site_manager
        and project.site_manager_user_id is not None
    ):
        manager = session.get(
            User,
            project.site_manager_user_id,
        )

        if (
            manager is not None
            and manager.is_active
            and manager.email
            and manager.email.strip()
        ):
            emails.add(manager.email.strip().lower())

    return sorted(emails)


def process_event(event_id: int) -> None:
    with SessionLocal() as session:
        settings = session.get(
            VPManholeNotificationSettings,
            1,
        )

        if settings is None or not settings.enabled:
            logger.info(
                "VPManhole-mailnotifikationer er deaktiveret. "
                "Hændelse %s springes over.",
                event_id,
            )
            return

        event = session.get(
            VPManholeNotificationEvent,
            event_id,
        )

        if event is None or event.status not in (
            "pending",
            "failed",
        ):
            return

        project = session.get(
            Project,
            event.project_id,
        )

        if project is None:
            logger.error(
                "Projekt mangler for hændelse %s",
                event_id,
            )
            return

        project_id = project.id
        if project_id in excluded_project_ids():
            logger.info("Projekt %s er udelukket fra mailafsendelse.", project_id)
            return
        project_name = project.name or project_id

        recipients = get_recipients(
            session,
            project,
            settings,
        )

        if not recipients:
            logger.warning(
                "Ingen mailmodtagere for projekt %s",
                project_id,
            )
            return

    # Kontroller billederne igen umiddelbart
    # inden færdigmeldingen.
    completion = (
        notification_service.check_project_completion(
            project_id
        )
    )

    if not completion.is_complete:
        logger.info("Projekt %s er ikke længere komplet.", project_id)
        return

    if not project_needs_notification(project_id):
        logger.info("Projekt %s er allerede fuldt eksporteret; ingen mail.", project_id)
        return

    # En hændelse kan kun overtages én gang.
    with SessionLocal() as session:
        claim = session.execute(
            update(VPManholeNotificationEvent)
            .where(
                VPManholeNotificationEvent.id == event_id,
                VPManholeNotificationEvent.status.in_(
                    ("pending", "failed")
                ),
            )
            .values(
                status="sending",
                last_attempt_at=now_utc(),
                last_error=None,
            )
            .returning(
                VPManholeNotificationEvent.id
            )
        ).scalar_one_or_none()

        session.commit()

    if claim is None:
        return

    base_url = os.environ.get(
        "VPMANHOLE_PUBLIC_URL",
        "https://vpmanhole.duckdns.org",
    ).rstrip("/")

    subject = (
        f"VPManhole: Billeddokumentation færdig "
        f"– {project_id}"
    )

    body = (
        "Billeddokumentationen er registreret som "
        "komplet for projektet.\n\n"
        f"Projekt: {project_id}\n"
        f"Navn: {project_name}\n"
        f"Renoveringsbrønde: "
        f"{completion.completed_manholes}"
        f"/{completion.total_manholes}\n\n"
        f"Åbn VPManhole:\n{base_url}/\n\n"
        "Log ind for at se og hente dokumentationen.\n"
    )

    try:
        send_mail(
            recipients=recipients,
            subject=subject,
            body=body,
        )

    except Exception as exc:
        logger.exception(
            "Mailafsendelse fejlede for %s",
            project_id,
        )

        with SessionLocal() as session:
            session.execute(
                update(VPManholeNotificationEvent)
                .where(
                    VPManholeNotificationEvent.id == event_id,
                    VPManholeNotificationEvent.status
                    == "sending",
                )
                .values(
                    status="failed",
                    attempt_count=(
                        VPManholeNotificationEvent.attempt_count
                        + 1
                    ),
                    last_error=str(exc)[:2000],
                    recipient_emails=", ".join(recipients),
                    updated_at=now_utc(),
                )
            )
            session.commit()

        return

    with SessionLocal() as session:
        session.execute(
            update(VPManholeNotificationEvent)
            .where(
                VPManholeNotificationEvent.id == event_id,
                VPManholeNotificationEvent.status
                == "sending",
            )
            .values(
                status="sent",
                attempt_count=(
                    VPManholeNotificationEvent.attempt_count
                    + 1
                ),
                recipient_emails=", ".join(recipients),
                sent_at=now_utc(),
                updated_at=now_utc(),
            )
        )
        session.commit()

    logger.info(
        "Mail accepteret af SMTP-relay for projekt %s",
        project_id,
    )

def excluded_project_ids() -> set[str]:
    """Projekter som ikke må få automatiske færdigmeldinger."""
    return {
        value.strip()
        for value in os.environ.get(
            "VPMANHOLE_NOTIFICATION_EXCLUDED_PROJECT_IDS", ""
        ).split(",")
        if value.strip()
    }


def project_needs_notification(project_id: str) -> bool:
    """
    True hvis projektet har komplette billeder,
    men ikke alle aktuelle billeder er eksporteret.
    """
    installations = (
        notification_service.vpmanhole_service
        .list_project_installations(project_id)
    )

    manhole_ids = {
        manhole["id"]
        for installation in installations
        for manhole in installation["manholes"]
    }

    if not manhole_ids:
        return False

    with SessionLocal() as session:
        deliveries = session.scalars(
            select(VPManholeDelivery).where(
                VPManholeDelivery.manhole_id.in_(manhole_ids)
            )
        ).all()

        if {d.manhole_id for d in deliveries} != manhole_ids:
            return True

        for delivery in deliveries:
            if delivery.last_exported_at is None:
                return True

            latest_upload = session.scalar(
                select(func.max(VPManholePhoto.uploaded_at))
                .where(VPManholePhoto.delivery_id == delivery.id)
            )

            if (
                latest_upload is not None
                and latest_upload > delivery.last_exported_at
            ):
                return True

    return False

def find_historical_notifications() -> list[str]:
    """
    Find komplette projekter uden eksisterende mailhændelse.

    Funktionen ændrer ikke databasen og sender ingen mails.
    """
    projects = DatabaseProjectRepository().list_projects()

    with SessionLocal() as session:
        notified_project_ids = set(
            session.scalars(
                select(VPManholeNotificationEvent.project_id)
            ).all()
        )

    candidates = []
    excluded = excluded_project_ids()

    for project in projects:
        project_id = project["id"]

        if project_id in notified_project_ids or project_id in excluded:
            continue

        completion = notification_service.check_project_completion(
            project_id
        )

        if not completion.is_complete:
            continue

        if not project_needs_notification(project_id):
            continue

        candidates.append(project_id)

    return candidates


def enqueue_historical_notifications() -> int:
    """Opret manglende hændelser uden dubletter; send ikke mails her."""
    candidates = find_historical_notifications()
    created = 0
    for project_id in candidates:
        # Genkontrollér, da billeder kan ændres under gennemgangen.
        if not notification_service.check_project_completion(project_id).is_complete:
            continue
        if not project_needs_notification(project_id):
            continue
        if project_id in excluded_project_ids():
            continue
        with SessionLocal() as session:
            stmt = (
                insert(VPManholeNotificationEvent)
                .values(project_id=project_id, status="pending")
                .on_conflict_do_nothing(
                    constraint="uq_vpmanhole_notification_event_project"
                )
                .returning(VPManholeNotificationEvent.id)
            )
            if session.scalar(stmt) is not None:
                created += 1
            session.commit()
    return created

def cleanup_exported_notifications() -> int:
    """Fjern usendte færdigmeldinger for fuldt eksporterede projekter."""
    from sqlalchemy import delete

    with SessionLocal() as session:
        project_ids = session.scalars(
            select(VPManholeNotificationEvent.project_id)
            .where(
                VPManholeNotificationEvent.status == "pending",
                VPManholeNotificationEvent.attempt_count == 0,
            )
        ).all()

    removed = 0

    for project_id in project_ids:
        completion = notification_service.check_project_completion(project_id)

        if not completion.is_complete:
            continue

        if project_needs_notification(project_id):
            continue

        with SessionLocal() as session:
            result = session.execute(
                delete(VPManholeNotificationEvent).where(
                    VPManholeNotificationEvent.project_id == project_id,
                    VPManholeNotificationEvent.status == "pending",
                    VPManholeNotificationEvent.attempt_count == 0,
                )
            )
            session.commit()
            removed += result.rowcount

    return removed

def main() -> None:
    with SessionLocal() as session:
        settings = session.get(VPManholeNotificationSettings, 1)

        if settings is None or not settings.enabled:
            logger.info(
                "VPManhole-mail er deaktiveret. Ingen mails sendes."
            )
            return

    # Find historiske, komplette projekter, som endnu
    # ikke har en mailhændelse.
    created = enqueue_historical_notifications()
    logger.info(
        "Oprettede %s historiske færdigmeldinger.",
        created,
    )

    # Hent ventende og tidligere fejlede mailhændelser.
    with SessionLocal() as session:
        event_ids = session.execute(
            select(VPManholeNotificationEvent.id)
            .where(
                VPManholeNotificationEvent.status.in_(
                    ("pending", "failed")
                )
            )
            .order_by(
                VPManholeNotificationEvent.created_at,
                VPManholeNotificationEvent.id,
            )
        ).scalars().all()

    logger.info(
        "Fandt %s færdigmeldinger i kø.",
        len(event_ids),
    )

    for event_id in event_ids:
        try:
            process_event(event_id)
        except Exception:
            logger.exception(
                "Uventet fejl ved hændelse %s",
                event_id,
            )


if __name__ == "__main__":
    import sys

    if "--dry-run" in sys.argv:
        candidates = find_historical_notifications()

        print(
            "Historiske projekter klar til færdigmelding: "
            f"{len(candidates)}"
        )

        for project_id in candidates:
            print(f"  {project_id}")
    else:
        main()