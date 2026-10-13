from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select, update

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.project import Project
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
    rows = (
        session.execute(
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
        )
        .scalars()
        .all()
    )

    emails = {
        user.email.strip().lower() for user in rows if user.email and user.email.strip()
    }

    if settings.include_site_manager and project.site_manager_user_id is not None:
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
            logger.info("Mailfunktionen er deaktiveret.")
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
    completion = notification_service.check_project_completion(project_id)

    if not completion.is_complete:
        logger.info(
            "Projekt %s er ikke længere komplet.",
            project_id,
        )
        return

    # En hændelse kan kun overtages én gang.
    with SessionLocal() as session:
        claim = session.execute(
            update(VPManholeNotificationEvent)
            .where(
                VPManholeNotificationEvent.id == event_id,
                VPManholeNotificationEvent.status.in_(("pending", "failed")),
            )
            .values(
                status="sending",
                last_attempt_at=now_utc(),
                last_error=None,
            )
            .returning(VPManholeNotificationEvent.id)
        ).scalar_one_or_none()

        session.commit()

    if claim is None:
        return

    base_url = os.environ.get(
        "VPMANHOLE_PUBLIC_URL",
        "https://vpmanhole.duckdns.org",
    ).rstrip("/")

    subject = f"VPManhole: Billeddokumentation færdig " f"– {project_id}"

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
                    VPManholeNotificationEvent.status == "sending",
                )
                .values(
                    status="failed",
                    attempt_count=(VPManholeNotificationEvent.attempt_count + 1),
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
                VPManholeNotificationEvent.status == "sending",
            )
            .values(
                status="sent",
                attempt_count=(VPManholeNotificationEvent.attempt_count + 1),
                recipient_emails=", ".join(recipients),
                sent_at=now_utc(),
                updated_at=now_utc(),
            )
        )
        session.commit()

    logger.info(
        "Mail accepteret af Graph for projekt %s",
        project_id,
    )


def main() -> None:
    with SessionLocal() as session:
        settings = session.get(
            VPManholeNotificationSettings,
            1,
        )

        if settings is None or not settings.enabled:
            logger.info("VPManhole-mail er deaktiveret. " "Ingen mails sendes.")
            return

        event_ids = (
            session.execute(
                select(VPManholeNotificationEvent.id)
                .where(VPManholeNotificationEvent.status.in_(("pending", "failed")))
                .order_by(
                    VPManholeNotificationEvent.created_at,
                    VPManholeNotificationEvent.id,
                )
            )
            .scalars()
            .all()
        )

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
    main()
