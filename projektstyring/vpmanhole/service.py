from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import Installation, Stretch
from projektstyring.backend.repositories.database_project_repository import (
    DatabaseProjectRepository,
)


OPEN_PROJECT_STATUSES = {
    "survey",
    "upcoming",
    "active",
}


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
        Henter aktive installationer og deres brønde til VPManhole.

        En brønd vises kun én gang pr. installation, selv om den
        indgår i flere stræk.
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

            result: list[dict[str, Any]] = []

            for installation in installations:
                manholes_by_id: dict[int, dict[str, Any]] = {}

                for stretch in installation.stretches:
                    for manhole in (
                        stretch.bottom_manhole,
                        stretch.top_manhole,
                    ):
                        if manhole is None or not manhole.active:
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
