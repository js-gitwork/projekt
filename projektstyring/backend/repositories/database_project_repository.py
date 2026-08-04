from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.database.import_project import import_project
from projektstyring.backend.db_models import (
    Installation,
    Project,
    ProjectTask,
    TaskAssignment,
    TaskQuantity,
)
from projektstyring.backend.survey_model import ensure_survey


def date_to_string(value: date | None) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def numeric_value(value: float) -> int | float:
    if float(value).is_integer():
        return int(value)

    return float(value)


class DatabaseProjectRepository:
    def list_projects(self) -> list[dict[str, Any]]:
        with SessionLocal() as session:
            statement = select(Project).order_by(
                Project.start_date.asc().nulls_last(),
                Project.id.asc(),
            )

            projects = session.scalars(statement).all()

            return [
                {
                    "id": project.id,
                    "name": project.name,
                    "customer": project.customer,
                    "city": project.city,
                    "start_date": date_to_string(
                        project.start_date
                    ),
                    "status": project.status,
                    # Bevares midlertidigt for kompatibilitet
                    # med kode, der tidligere modtog filnavnet.
                    "file": None,
                }
                for project in projects
            ]

    def load_project(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        with SessionLocal() as session:
            statement = (
                select(Project)
                .where(Project.id == project_id)
                .options(
                    selectinload(Project.installations)
                    .selectinload(Installation.tasks)
                    .selectinload(ProjectTask.quantities),

                    selectinload(Project.installations)
                    .selectinload(Installation.tasks)
                    .selectinload(
                        ProjectTask.task_assignments
                    ),

                    selectinload(Project.installations)
                    .selectinload(Installation.progress),

                    selectinload(Project.installations)
                    .selectinload(Installation.stretches),
                )
            )

            project = session.scalar(statement)

            if project is None:
                raise FileNotFoundError(
                    f"Projektet '{project_id}' findes ikke."
                )

            project_data = self._project_to_dict(project)

        return ensure_survey(project_data)

    def load_all_projects(self) -> list[dict[str, Any]]:
        projects = []

        for project_info in self.list_projects():
            projects.append(
                self.load_project(project_info["id"])
            )

        return projects

    def save_project(
        self,
        project: dict[str, Any],
    ) -> dict[str, Any]:
        project_id = str(project["id"])

        with SessionLocal() as session:
            try:
                import_project(
                    project,
                    session=session,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise

        return self.load_project(project_id)

    def update_project_fields(
        self,
        project_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        allowed_fields = {
            "name",
            "customer",
            "city",
            "start_date",
            "status",
            "notes",
        }

        with SessionLocal() as session:
            project = session.get(Project, project_id)

            if project is None:
                raise FileNotFoundError(
                    f"Projektet '{project_id}' findes ikke."
                )

            for key, value in updates.items():
                if key not in allowed_fields:
                    continue

                if value in (None, ""):
                    continue

                if key == "start_date":
                    if isinstance(value, date):
                        project.start_date = value
                    else:
                        project.start_date = (
                            date.fromisoformat(str(value))
                        )
                    continue

                setattr(project, key, value)

            session.commit()

        return self.load_project(project_id)

    def update_project_status(
        self,
        project_id: str,
        status: str,
    ) -> dict[str, Any]:
        return self.update_project_fields(
            project_id,
            {
                "status": status,
            },
        )

    def delete_project(
        self,
        project_id: str,
    ) -> bool:
        """
        Permanent sletning.

        Bør kun bruges til testprojekter. Rigtige projekter bør
        senere arkiveres gennem status og archived_at.
        """
        with SessionLocal() as session:
            project = session.get(Project, project_id)

            if project is None:
                return False

            installation_ids = list(
                session.scalars(
                    select(Installation.id).where(
                        Installation.project_id
                        == project_id
                    )
                )
            )

            task_ids = list(
                session.scalars(
                    select(ProjectTask.id).where(
                        ProjectTask.project_id
                        == project_id
                    )
                )
            )

            try:
                if task_ids:
                    session.execute(
                        delete(TaskAssignment).where(
                            TaskAssignment.project_task_id.in_(
                                task_ids
                            )
                        )
                    )

                    session.execute(
                        delete(TaskQuantity).where(
                            TaskQuantity.project_task_id.in_(
                                task_ids
                            )
                        )
                    )

                    session.execute(
                        delete(ProjectTask).where(
                            ProjectTask.id.in_(task_ids)
                        )
                    )

                if installation_ids:
                    session.execute(
                        delete(Installation).where(
                            Installation.id.in_(
                                installation_ids
                            )
                        )
                    )

                session.delete(project)
                session.commit()

                return True

            except Exception:
                session.rollback()
                raise

    def _project_to_dict(
        self,
        project: Project,
    ) -> dict[str, Any]:
        installations = sorted(
            project.installations,
            key=lambda item: (
                item.sequence,
                item.installation_no,
            ),
        )

        task_assignments: dict[
            str,
            dict[str, set[str]],
        ] = defaultdict(
            lambda: defaultdict(set)
        )

        installation_data = []

        for installation in installations:
            installation_data.append(
                {
                    "id": installation.installation_no,
                    "sequence": installation.sequence,
                    "active": installation.active,
                    "hoveddato": date_to_string(
                        installation.hoveddato
                    ),
                    "expected_stik": (
                        installation.expected_stik
                    ),
                    "active_stik": (
                        installation.active_stik
                    ),
                    "opened_stik": (
                        installation.opened_stik
                    ),
                    "langhatte": installation.langhatte,
                    "korthatte_extra": (
                        installation.korthatte_extra
                    ),
                    "broende": installation.broende,
                    "bronde_total": installation.bronde_total,
                    "hovedledning_meter": (
                        installation.hovedledning_meter
                    ),
                    "main_length_m": (
                        installation.hovedledning_meter
                    ),
                    "progress": self._progress_to_dict(
                        installation
                    ),
                    "stretches": self._stretches_to_list(
                        installation
                    ),
                    "notes": installation.notes,
                }
            )

            for task in installation.tasks:
                if not task.active:
                    continue

                for assignment in task.task_assignments:
                    if not assignment.active:
                        continue

                    task_assignments[
                        task.task_type_id
                    ][
                        assignment.team_id
                    ].add(
                        installation.installation_no
                    )

        formatted_assignments = {}

        for task_type_id, teams in (
            task_assignments.items()
        ):
            formatted_assignments[task_type_id] = [
                {
                    "team": team_id,
                    "installations": sorted(
                        installation_numbers,
                        key=self._installation_sort_key,
                    ),
                }
                for team_id, installation_numbers in sorted(
                    teams.items()
                )
            ]

        return {
            "id": project.id,
            "name": project.name,
            "customer": project.customer,
            "city": project.city,
            "start_date": date_to_string(
                project.start_date
            ),
            "status": project.status,
            "notes": project.notes,
            "installations": installation_data,
            "task_assignments": formatted_assignments,
        }

    @staticmethod
    def _progress_to_dict(
        installation: Installation,
    ) -> dict[str, float | None]:
        progress = installation.progress

        if progress is None:
            return {
                "opmaaling": None,
                "forarbejde": None,
                "stikopmaaling": None,
                "hovedledning": None,
                "stikaabning": None,
            }

        return {
            "opmaaling": progress.opmaaling,
            "forarbejde": progress.forarbejde,
            "stikopmaaling": progress.stikopmaaling,
            "hovedledning": progress.hovedledning,
            "stikaabning": progress.stikaabning,
        }

    @staticmethod
    def _stretches_to_list(
        installation: Installation,
    ) -> list[dict[str, Any]]:
        return [
            {
                "from_brond": stretch.from_brond,
                "to_brond": stretch.to_brond,
                "length_m": stretch.length_m,
                "dimension": stretch.dimension,
                "material": stretch.material,
                "stik": stretch.stik,
                "notes": stretch.notes,
                **(stretch.metadata_data or {}),
            }
            for stretch in sorted(
                installation.stretches,
                key=lambda item: item.sequence,
            )
        ]

    @staticmethod
    def _installation_sort_key(
        installation_no: str,
    ) -> tuple[int, int | str]:
        try:
            return 0, int(installation_no)
        except ValueError:
            return 1, installation_no
