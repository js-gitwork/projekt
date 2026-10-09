from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import (
    Installation,
    ManholeWork,
    Stretch,
)
from projektstyring.backend.repositories.database_project_repository import (
    DatabaseProjectRepository,
)


OPEN_PROJECT_STATUSES = {
    "survey",
    "upcoming",
    "active",
}

def normalize_installation_no(value: object) -> str:
    """
    Normaliserer installationsnumre fra C5.

    Eksempler:
        "1,0" -> "1"
        "2.0" -> "2"
        3     -> "3"
    """
    from decimal import Decimal, InvalidOperation

    text = str(value or "").strip().replace(",", ".")

    if not text:
        return ""

    try:
        number = Decimal(text)
        if number == number.to_integral_value():
            return str(int(number))
    except InvalidOperation:
        pass

    return text.casefold()

class VPManholeService:
    def __init__(self) -> None:
        self.project_repository = DatabaseProjectRepository()

    def list_open_projects(self) -> list[dict[str, Any]]:
        projects = self.project_repository.list_projects()

        return [
            project
            for project in projects
            if project.get("status") in OPEN_PROJECT_STATUSES
        ]

    def list_project_installations(
        self,
        project_id: str,
    ) -> list[dict[str, Any]]:
        """
        Henter aktive installationer og deres renoveringsbrønde.

        En brønd vises kun under den installation,
        hvor renoveringen er registreret i C5.
        """
        with SessionLocal() as session:
            statement = (
                select(Installation)
                .where(
                    Installation.project_id == project_id,
                    Installation.active.is_(True),
                )
                .options(
                    selectinload(Installation.stretches)
                    .selectinload(Stretch.bottom_manhole),
                    selectinload(Installation.stretches)
                    .selectinload(Stretch.top_manhole),
                )
                .order_by(Installation.sequence.asc())
            )

            installations = session.scalars(statement).all()

            renovation_works = session.scalars(
                select(ManholeWork)
                .join(ManholeWork.manhole)
                .where(
                    ManholeWork.work_type == "broendrenovering",
                    ManholeWork.manhole.has(
                        project_id=project_id
                    ),
                )
                .order_by(ManholeWork.id.desc())
            ).all()

            # Seneste registrering pr. brønd.
            latest_work_by_manhole = {}

            for work in renovation_works:
                latest_work_by_manhole.setdefault(
                    work.manhole_id,
                    work,
                )

            result: list[dict[str, Any]] = []

            for installation in installations:
                installation_no = normalize_installation_no(
                    installation.installation_no
                )

                manholes_by_id: dict[int, dict[str, Any]] = {}

                for stretch in installation.stretches:
                    for manhole in (
                        stretch.bottom_manhole,
                        stretch.top_manhole,
                    ):
                        if manhole is None or not manhole.active:
                            continue

                        work = latest_work_by_manhole.get(
                            manhole.id
                        )

                        if work is None:
                            continue

                        metadata = work.metadata_data or {}

                        renovation_type = str(
                            metadata.get("renovation_type") or ""
                        ).strip().casefold()

                        if renovation_type not in {
                            "total",
                            "ds437",
                        }:
                            continue

                        work_installation_no = (
                            normalize_installation_no(
                                metadata.get("installation_no")
                            )
                        )

                        if work_installation_no != installation_no:
                            continue

                        manholes_by_id[manhole.id] = {
                            "id": manhole.id,
                            "manhole_no": manhole.manhole_no,
                        }

                manholes = sorted(
                    manholes_by_id.values(),
                    key=lambda item: item["manhole_no"],
                )

                result.append(
                    {
                        "id": installation.id,
                        "installation_no": installation.installation_no,
                        "manholes": manholes,
                    }
                )

            return result