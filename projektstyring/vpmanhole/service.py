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

        result = []

        for project in projects:
            if project.get("status") not in OPEN_PROJECT_STATUSES:
                continue

            project_id = project.get("id")
            if not project_id:
                continue

            installations = self.list_project_installations(project_id)

            if any(installation["manholes"] for installation in installations):
                result.append(project)

        return result

    def list_project_installations(
        self,
        project_id: str,
    ) -> list[dict[str, Any]]:
        """
        Henter aktive installationer og deres renoveringsbrønde.

        Brøndene knyttes til installationen via installationsnummeret
        i C5-arbejdsregistreringen.

        Der kræves ikke brøndstræk. Funktionen understøtter derfor
        både almindelige projekter og rene brøndrenoveringsprojekter.
        """
        with SessionLocal() as session:
            installations = session.scalars(
                select(Installation)
                .where(
                    Installation.project_id == project_id,
                    Installation.active.is_(True),
                )
                .order_by(Installation.sequence.asc())
            ).all()

            renovation_works = session.scalars(
                select(ManholeWork)
                .join(ManholeWork.manhole)
                .where(
                    ManholeWork.work_type == "broendrenovering",
                    ManholeWork.manhole.has(project_id=project_id),
                )
                .options(
                    selectinload(ManholeWork.manhole)
                )
                .order_by(ManholeWork.id.desc())
            ).all()

            # Behold kun den seneste registrering for hver brønd.
            latest_work_by_manhole = {}

            for work in renovation_works:
                latest_work_by_manhole.setdefault(
                    work.manhole_id,
                    work,
                )

            # Fordel brøndene efter C5-installationsnummer.
            manholes_by_installation: dict[
                str, dict[int, dict[str, Any]]
            ] = {}

            for work in latest_work_by_manhole.values():
                manhole = work.manhole

                if manhole is None or not manhole.active:
                    continue

                metadata = work.metadata_data or {}

                renovation_type = str(
                    metadata.get("renovation_type") or ""
                ).strip().casefold()

                if renovation_type not in {"total", "ds437"}:
                    continue

                installation_no = normalize_installation_no(
                    metadata.get("installation_no")
                )

                if not installation_no:
                    continue

                manholes_by_installation.setdefault(
                    installation_no, {}
                )[manhole.id] = {
                    "id": manhole.id,
                    "manhole_no": manhole.manhole_no,
                }

            result: list[dict[str, Any]] = []

            for installation in installations:
                installation_no = normalize_installation_no(
                    installation.installation_no
                )

                manholes = sorted(
                    manholes_by_installation.get(
                        installation_no, {}
                    ).values(),
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