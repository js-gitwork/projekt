
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.vpmanhole import (
    VPManholeDelivery,
    VPManholePhoto,
)
from projektstyring.backend.db_models.vpmanhole_notification import (
    VPManholeNotificationEvent,
)
from projektstyring.vpmanhole.service import VPManholeService


logger = logging.getLogger(__name__)

REQUIRED_PHOTO_TYPES = frozenset(
    {"before", "after", "cover"}
)


@dataclass(frozen=True)
class ProjectPhotoCompletion:
    project_id: str
    total_manholes: int
    completed_manholes: int
    missing_manholes: int

    @property
    def is_complete(self) -> bool:
        return (
            self.total_manholes > 0
            and self.missing_manholes == 0
        )


class VPManholeNotificationService:
    def __init__(self) -> None:
        self.vpmanhole_service = VPManholeService()

    @staticmethod
    def get_photo_types_for_manholes(
        manhole_ids: set[int],
    ) -> dict[int, set[str]]:
        """
        Henter de obligatoriske billedtyper
        for en samling fysiske brønde.
        """

        result: dict[int, set[str]] = {
            manhole_id: set()
            for manhole_id in manhole_ids
        }

        if not manhole_ids:
            return result

        with SessionLocal() as session:
            rows = session.execute(
                select(
                    VPManholeDelivery.manhole_id,
                    VPManholePhoto.photo_type,
                )
                .join(
                    VPManholePhoto,
                    VPManholePhoto.delivery_id
                    == VPManholeDelivery.id,
                )
                .where(
                    VPManholeDelivery.manhole_id.in_(
                        manhole_ids
                    ),
                    VPManholePhoto.photo_type.in_(
                        REQUIRED_PHOTO_TYPES
                    ),
                )
            ).all()

        for manhole_id, photo_type in rows:
            result[manhole_id].add(photo_type)

        return result

    @staticmethod
    def _summarize(
        manhole_ids: set[int],
        photo_types: dict[int, set[str]],
    ) -> dict[str, int | bool]:
        """
        Én fælles definition af færdigstatus.
        """

        total = len(manhole_ids)

        completed = sum(
            REQUIRED_PHOTO_TYPES.issubset(
                photo_types.get(manhole_id, set())
            )
            for manhole_id in manhole_ids
        )

        missing = total - completed

        return {
            "total": total,
            "completed": completed,
            "missing": missing,
            "complete": total > 0 and missing == 0,
            "has_manholes": total > 0,
        }

    def _build_status(
        self,
        project_installations: dict[
            str, list[dict[str, Any]]
        ],
    ) -> tuple[
        dict[str, dict[str, int | bool]],
        dict[str, dict[int, dict[str, int | bool]]],
    ]:
        """
        Beregner projekt- og installationsstatus
        ud fra samme billedopslag.
        """

        all_manhole_ids: set[int] = set()

        for installations in project_installations.values():
            for installation in installations:
                all_manhole_ids.update(
                    manhole["id"]
                    for manhole in installation["manholes"]
                )

        photo_types = self.get_photo_types_for_manholes(
            all_manhole_ids
        )

        project_status = {}
        installation_status = {}

        for project_id, installations in (
            project_installations.items()
        ):
            project_manhole_ids: set[int] = set()
            per_installation = {}

            for installation in installations:
                manhole_ids = {
                    manhole["id"]
                    for manhole in installation["manholes"]
                }

                project_manhole_ids.update(manhole_ids)

                per_installation[installation["id"]] = (
                    self._summarize(
                        manhole_ids,
                        photo_types,
                    )
                )

            project_status[project_id] = self._summarize(
                project_manhole_ids,
                photo_types,
            )

            installation_status[project_id] = per_installation

        return project_status, installation_status

    def check_project_completion(
        self,
        project_id: str,
    ) -> ProjectPhotoCompletion:
        installations = (
            self.vpmanhole_service.list_project_installations(
                project_id
            )
        )

        project_status, _ = self._build_status(
            {project_id: installations}
        )

        status = project_status[project_id]

        return ProjectPhotoCompletion(
            project_id=project_id,
            total_manholes=int(status["total"]),
            completed_manholes=int(status["completed"]),
            missing_manholes=int(status["missing"]),
        )

    def get_installation_completion(
        self,
        project_id: str,
    ) -> dict[int, dict[str, int | bool]]:
        installations = (
            self.vpmanhole_service.list_project_installations(
                project_id
            )
        )

        _, installation_status = self._build_status(
            {project_id: installations}
        )

        return installation_status[project_id]

    def get_project_completion_overview(
        self,
        projects: list[dict],
    ) -> dict[str, dict[str, int | bool]]:
        """
        Beregner status for projektlisten.

        Alle billedtyper hentes samlet.
        """

        project_installations = {}

        for project in projects:
            project_id = project["id"]

            project_installations[project_id] = (
                self.vpmanhole_service.list_project_installations(
                    project_id
                )
            )

        project_status, _ = self._build_status(
            project_installations
        )

        return project_status

    def enqueue_if_complete(
        self,
        project_id: str,
    ) -> ProjectPhotoCompletion:
        """
        Registrerer højst én færdigmelding pr.
        projekt. Sender ikke mail.
        """

        completion = self.check_project_completion(
            project_id
        )

        if not completion.is_complete:
            return completion

        with SessionLocal() as session:
            statement = (
                insert(VPManholeNotificationEvent)
                .values(
                    project_id=project_id,
                    status="pending",
                    attempt_count=0,
                )
                .on_conflict_do_nothing(
                    constraint=(
                        "uq_vpmanhole_notification_event_project"
                    ),
                )
            )

            session.execute(statement)
            session.commit()

        logger.info(
            "Færdigmelding registreret: %s (%s/%s)",
            project_id,
            completion.completed_manholes,
            completion.total_manholes,
        )

        return completion


notification_service = VPManholeNotificationService()
