from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Any

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.repositories.planning_scenario_repository import (
    PlanningScenarioRepository,
)


class PlanningScenarioService:
    """
    Forretningslogik for planlægningsscenarier.

    Et scenarie er et arbejdsområde, hvor flere forslag kan beregnes
    og revideres uden at ændre de gældende projekter.

    Scenarierevisioner:
    - dokumenterer forslag og overvejelser
    - må ikke ændre produktionsprojekterne
    - opretter ikke før-/eftersnapshots

    Når en revision senere godkendes:
    - oprettes snapshot før ændringen for hvert berørt projekt
    - projektændringerne udføres
    - planen valideres
    - snapshot efter ændringen oprettes
    - beslutningen og scenarierevisionen forbindes
    """

    EDITABLE_STATUSES = {
        "draft",
        "rejected",
    }

    FINAL_STATUSES = {
        "committed",
        "cancelled",
    }

    def __init__(
        self,
        *,
        scenario_repository: PlanningScenarioRepository | None = None,
        project_repository: ProjectRepository | None = None,
    ):
        self.scenario_repository = (
            scenario_repository
            or PlanningScenarioRepository()
        )
        self.project_repository = (
            project_repository
            or ProjectRepository()
        )

    # ------------------------------------------------------------
    # Oprettelse
    # ------------------------------------------------------------

    def create_scenario(
        self,
        *,
        project_ids: list[str],
        title: str = "Nyt planlægningsscenarie",
        description: str = "",
        created_by: str | None = None,
        user_message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Opretter et scenarie med de valgte projekter og revision 1.

        Projekternes aktuelle tilstand kopieres til scenario_projects.
        De virkelige projekter bliver ikke ændret.
        """

        normalized_project_ids = (
            self._normalize_project_ids(project_ids)
        )

        if not normalized_project_ids:
            raise ValueError(
                "Et planlægningsscenarie skal indeholde "
                "mindst ét projekt."
            )

        with SessionLocal() as session:
            try:
                projects = [
                    self._load_project(project_id)
                    for project_id
                    in normalized_project_ids
                ]

                scenario = (
                    self.scenario_repository.create_scenario(
                        title=title,
                        description=description,
                        created_by=created_by,
                        metadata={
                            **deepcopy(metadata or {}),
                            "project_count": len(projects),
                        },
                        session=session,
                    )
                )

                for sequence, project in enumerate(
                    projects,
                    start=1,
                ):
                    self.scenario_repository.add_project(
                        scenario_id=scenario.id,
                        project_id=project["id"],
                        base_project_state=project,
                        sequence=sequence,
                        metadata={
                            "project_name": project.get(
                                "name",
                                "",
                            ),
                            "project_status": project.get(
                                "status",
                                "",
                            ),
                        },
                        session=session,
                    )

                revision = (
                    self.scenario_repository.create_revision(
                        scenario_id=scenario.id,
                        reason="Scenariet oprettet",
                        user_message=user_message,
                        ai_summary=(
                            "Første revision baseret på "
                            "projekternes gældende tilstand."
                        ),
                        calculated_result={
                            "projects": deepcopy(projects),
                            "activities": [],
                        },
                        conflicts=[],
                        warnings=[],
                        constraints=[],
                        activities=[],
                        changes=[],
                        metadata={
                            "revision_type": "initial",
                        },
                        session=session,
                    )
                )

                session.commit()

                scenario_id = scenario.id
                revision_id = revision.id

            except Exception:
                session.rollback()
                raise

        return self.get_scenario(
            scenario_id,
            revision_id=revision_id,
        )

    # ------------------------------------------------------------
    # Revisioner
    # ------------------------------------------------------------

    def create_revision(
        self,
        *,
        scenario_id: str,
        user_message: str,
        reason: str = "",
        ai_summary: str = "",
        calculated_result: dict[str, Any] | None = None,
        activities: list[dict[str, Any]] | None = None,
        changes: list[dict[str, Any]] | None = None,
        conflicts: list[dict[str, Any]] | None = None,
        warnings: list[dict[str, Any]] | None = None,
        constraints: list[dict[str, Any]] | None = None,
        planner_version: str = "current",
        week_year: int | None = None,
        week_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Opretter en ny revision i et eksisterende kladdescenarie.

        Den tidligere revision overskrives aldrig.
        """

        with SessionLocal() as session:
            try:
                scenario = (
                    self.scenario_repository.require_scenario(
                        scenario_id,
                        include_projects=True,
                        session=session,
                    )
                )

                self._require_editable_scenario(
                    scenario
                )

                revision = (
                    self.scenario_repository.create_revision(
                        scenario_id=scenario_id,
                        reason=reason,
                        user_message=user_message,
                        ai_summary=ai_summary,
                        calculated_result=(
                            calculated_result or {}
                        ),
                        activities=activities or [],
                        changes=changes or [],
                        conflicts=conflicts or [],
                        warnings=warnings or [],
                        constraints=constraints or [],
                        planner_version=planner_version,
                        week_year=week_year,
                        week_number=week_number,
                        metadata=metadata or {},
                        session=session,
                    )
                )

                session.commit()
                revision_id = revision.id

            except Exception:
                session.rollback()
                raise

        return self.get_scenario(
            scenario_id,
            revision_id=revision_id,
        )

    def reject_active_revision(
        self,
        scenario_id: str,
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        """
        Markerer den aktive revision som afvist, men bevarer scenariet.

        Det gør det muligt at fortsætte samtalen og oprette en revideret
        løsning uden at formulere hele scenariet igen.
        """

        with SessionLocal() as session:
            try:
                scenario = (
                    self.scenario_repository.require_scenario(
                        scenario_id,
                        include_projects=True,
                        session=session,
                    )
                )

                self._require_editable_scenario(
                    scenario
                )

                revision = (
                    self.scenario_repository.get_active_revision(
                        scenario_id,
                        session=session,
                    )
                )

                if revision is None:
                    raise ValueError(
                        "Scenariet har ingen aktiv revision."
                    )

                revision.status = "rejected"

                revision.metadata_data = {
                    **deepcopy(
                        revision.metadata_data or {}
                    ),
                    "rejection_reason": reason.strip(),
                }

                scenario.status = "draft"

                session.commit()
                revision_id = revision.id

            except Exception:
                session.rollback()
                raise

        return self.get_scenario(
            scenario_id,
            revision_id=revision_id,
        )

    def select_revision(
        self,
        *,
        scenario_id: str,
        revision_number: int,
    ) -> dict[str, Any]:
        """
        Gør en tidligere revision til scenariets aktive forslag.
        """

        scenario = (
            self.scenario_repository.require_scenario(
                scenario_id,
            )
        )

        self._require_editable_scenario(
            scenario
        )

        self.scenario_repository.set_active_revision(
            scenario_id=scenario_id,
            revision_number=revision_number,
        )

        return self.get_scenario(
            scenario_id
        )

    # ------------------------------------------------------------
    # Læsning
    # ------------------------------------------------------------

    def get_scenario(
        self,
        scenario_id: str,
        *,
        revision_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Returnerer scenariet i en stabil struktur til API og frontend.
        """

        with SessionLocal() as session:
            scenario = (
                self.scenario_repository.require_scenario(
                    scenario_id,
                    include_projects=True,
                    include_revisions=True,
                    session=session,
                )
            )

            if revision_id:
                revision = (
                    self.scenario_repository.get_revision(
                        revision_id,
                        session=session,
                    )
                )

                if (
                    revision is None
                    or revision.scenario_id
                    != scenario_id
                ):
                    raise FileNotFoundError(
                        f"Revisionen '{revision_id}' "
                        "findes ikke i scenariet."
                    )
            else:
                revision = (
                    self.scenario_repository.get_active_revision(
                        scenario_id,
                        session=session,
                    )
                )

            return self._serialize_scenario(
                scenario,
                revision,
            )

    def list_scenarios(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Returnerer en kompakt liste over scenarier.
        """

        scenarios = (
            self.scenario_repository.list_scenarios(
                status=status,
                limit=limit,
            )
        )

        return [
            {
                "id": scenario.id,
                "title": scenario.title,
                "status": scenario.status,
                "created_by": scenario.created_by,
                "active_revision_number": (
                    scenario.active_revision_number
                ),
                "project_ids": [
                    project.project_id
                    for project
                    in scenario.projects
                ],
                "created_at": (
                    scenario.created_at.isoformat()
                    if scenario.created_at
                    else None
                ),
                "updated_at": (
                    scenario.updated_at.isoformat()
                    if scenario.updated_at
                    else None
                ),
            }
            for scenario in scenarios
        ]

    # ------------------------------------------------------------
    # Interne hjælpefunktioner
    # ------------------------------------------------------------

    def _load_project(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        """
        Henter et projekt og sikrer, at resultatet er en dictionary.
        """

        project = (
            self.project_repository.load_project(
                project_id
            )
        )

        if not project:
            raise FileNotFoundError(
                f"Projektet '{project_id}' findes ikke."
            )

        if not isinstance(project, dict):
            raise TypeError(
                f"Projektet '{project_id}' blev ikke "
                "returneret som en dictionary."
            )

        return deepcopy(project)

    def _normalize_project_ids(
        self,
        project_ids: list[str],
    ) -> list[str]:
        """
        Fjerner tomme værdier og dubletter uden at ændre rækkefølgen.
        """

        result = []

        for value in project_ids or []:
            project_id = str(
                value or ""
            ).strip()

            if (
                project_id
                and project_id not in result
            ):
                result.append(project_id)

        return result

    def _require_editable_scenario(
        self,
        scenario,
    ) -> None:
        """
        Forhindrer ændringer i afsluttede scenarier.
        """

        if scenario.status in self.FINAL_STATUSES:
            raise ValueError(
                f"Scenariet har status "
                f"'{scenario.status}' og kan ikke ændres."
            )

    def _serialize_scenario(
        self,
        scenario,
        revision,
    ) -> dict[str, Any]:
        """
        Serialiserer scenariet til den permanente datakontrakt.
        """

        projects = [
            {
                "project_id": item.project_id,
                "sequence": item.sequence,
                "base_snapshot_id": (
                    item.base_snapshot_id
                ),
                "base_project_state": deepcopy(
                    item.base_project_state
                ),
                "metadata": deepcopy(
                    item.metadata_data or {}
                ),
            }
            for item in scenario.projects
        ]

        revisions = [
            {
                "id": item.id,
                "revision_number": (
                    item.revision_number
                ),
                "status": item.status,
                "reason": item.reason,
                "user_message": item.user_message,
                "ai_summary": item.ai_summary,
                "created_at": (
                    item.created_at.isoformat()
                    if item.created_at
                    else None
                ),
            }
            for item in scenario.revisions
        ]

        result = {
            "scenario_id": scenario.id,
            "title": scenario.title,
            "description": scenario.description,
            "status": scenario.status,
            "created_by": scenario.created_by,
            "approved_by": scenario.approved_by,
            "approved_at": self._isoformat(
                scenario.approved_at
            ),
            "committed_at": self._isoformat(
                scenario.committed_at
            ),
            "active_revision_number": (
                scenario.active_revision_number
            ),
            "created_at": self._isoformat(
                scenario.created_at
            ),
            "updated_at": self._isoformat(
                scenario.updated_at
            ),
            "projects": projects,
            "revisions": revisions,
            "active_revision": None,
        }

        if revision is not None:
            result["active_revision"] = (
                self._serialize_revision(
                    revision
                )
            )

        return result

    def _serialize_revision(
        self,
        revision,
    ) -> dict[str, Any]:
        """
        Serialiserer én komplet scenarierevision.
        """

        activities = [
            {
                "id": activity.id,
                "sequence": activity.sequence,
                "project_id": activity.project_id,
                "installation_no": (
                    activity.installation_no
                ),
                "task_type": activity.task_type,
                "team_id": activity.team_id,
                "current_start": self._isoformat(
                    activity.current_start
                ),
                "current_end": self._isoformat(
                    activity.current_end
                ),
                "proposed_start": self._isoformat(
                    activity.proposed_start
                ),
                "proposed_end": self._isoformat(
                    activity.proposed_end
                ),
                "change_status": (
                    activity.change_status
                ),
                "status": activity.status,
                "quantity": deepcopy(
                    activity.quantity_data or {}
                ),
                "notes": activity.notes,
                "is_locked": activity.is_locked,
                "lock_reason": (
                    activity.lock_reason
                ),
                "metadata": deepcopy(
                    activity.metadata_data or {}
                ),
            }
            for activity in revision.activities
        ]

        changes = [
            {
                "id": change.id,
                "sequence": change.sequence,
                "project_id": change.project_id,
                "change_type": change.change_type,
                "target_type": change.target_type,
                "target_id": change.target_id,
                "status": change.status,
                "reason": change.reason,
                "before": deepcopy(
                    change.before_data
                ),
                "after": deepcopy(
                    change.after_data
                ),
                "metadata": deepcopy(
                    change.metadata_data or {}
                ),
            }
            for change in revision.changes
        ]

        return {
            "id": revision.id,
            "revision_number": (
                revision.revision_number
            ),
            "status": revision.status,
            "reason": revision.reason,
            "user_message": revision.user_message,
            "ai_summary": revision.ai_summary,
            "planner_version": (
                revision.planner_version
            ),
            "week_year": revision.week_year,
            "week_number": revision.week_number,
            "calculated_result": deepcopy(
                revision.calculated_result or {}
            ),
            "activities": activities,
            "changes": changes,
            "conflicts": deepcopy(
                revision.conflicts or []
            ),
            "warnings": deepcopy(
                revision.warnings or []
            ),
            "constraints": deepcopy(
                revision.constraints or []
            ),
            "metadata": deepcopy(
                revision.metadata_data or {}
            ),
            "created_at": self._isoformat(
                revision.created_at
            ),
        }

    def _isoformat(
        self,
        value: date | datetime | None,
    ) -> str | None:
        if value is None:
            return None

        return value.isoformat()
