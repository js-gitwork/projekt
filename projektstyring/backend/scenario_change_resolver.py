from __future__ import annotations

from copy import deepcopy
from typing import Any

from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.repositories.technical_asset_repository import (
    TechnicalAssetRepository,
)
from projektstyring.backend.repositories.team_repository import TeamRepository


class ScenarioChangeResolver:
    """
    Forankrer AI-fortolkede ændringer i systemets faktiske data.

    Interpreteren må gerne forstå menneskelige betegnelser som:

    - "Led 1"
    - "Filt Øst"
    - "Herslev"

    Resolveren omsætter dem til de kanoniske id'er, som databasen og
    planmotoren bruger:

    - "led1"
    - "filt_oest"
    - "V165460"

    Resolveren:
    - slår projekter og hold op
    - validerer installationer
    - validerer opgavetyper
    - kontrollerer holdets tilladelser
    - afviser tvetydige referencer
    - ændrer ikke databasen
    """

    SUPPORTED_CHANGE_TYPES = {
        "project_field_change",
        "installation_field_change",
        "manhole_field_change",
        "task_assignment_change",
    }

    def __init__(
        self,
        *,
        project_repository: ProjectRepository | None = None,
        team_repository: TeamRepository | None = None,
        technical_asset_repository: TechnicalAssetRepository | None = None,
    ):
        self.project_repository = (
            project_repository
            or ProjectRepository()
        )

        self.team_repository = (
            team_repository
            or TeamRepository()
        )

        self.technical_asset_repository = (
            technical_asset_repository
            or TechnicalAssetRepository()
        )
    # ------------------------------------------------------------
    # Offentlig indgang
    # ------------------------------------------------------------

    def resolve_changes(
        self,
        changes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Returnerer et valideret ændringssæt med kanoniske id'er.
        """

        if not isinstance(changes, list):
            raise TypeError(
                "changes skal være en liste."
            )

        if not changes:
            raise ValueError(
                "Der er ingen ændringer at validere."
            )

        projects = self._load_projects()
        teams = self._load_teams()

        resolved = []

        for sequence, change in enumerate(
            changes,
            start=1,
        ):
            resolved.append(
                self._resolve_change(
                    change=change,
                    sequence=sequence,
                    projects=projects,
                    teams=teams,
                )
            )

        return resolved

    # ------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------

    def _resolve_change(
        self,
        *,
        change: dict[str, Any],
        sequence: int,
        projects: dict[str, dict[str, Any]],
        teams: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(change, dict):
            raise TypeError(
                f"Ændring {sequence} er ikke en dictionary."
            )

        change_type = str(
            change.get("change_type") or ""
        ).strip()

        if change_type not in self.SUPPORTED_CHANGE_TYPES:
            raise ValueError(
                f"Ændringstypen '{change_type}' "
                "understøttes ikke."
            )

        resolved = deepcopy(change)

        project_id = self._resolve_project_id(
            change.get("project_id"),
            projects,
        )

        resolved["project_id"] = project_id

        project = projects[project_id]

        if change_type == "project_field_change":
            return self._resolve_project_field_change(
                resolved,
                project,
            )

        if change_type == "installation_field_change":
            return self._resolve_installation_field_change(
                resolved,
                project,
            )

        if change_type == "manhole_field_change":
            return self._resolve_manhole_field_change(
                resolved,
                project,
            )

        if change_type == "task_assignment_change":
            return self._resolve_task_assignment_change(
                resolved,
                project,
                teams,
            )

        raise ValueError(
            f"Ændringstypen '{change_type}' "
            "kunne ikke behandles."
        )

    # ------------------------------------------------------------
    # Projektændringer
    # ------------------------------------------------------------

    def _resolve_project_field_change(
        self,
        change: dict[str, Any],
        project: dict[str, Any],
    ) -> dict[str, Any]:
        after = change.get("after")

        if not isinstance(after, dict):
            raise ValueError(
                "Projektændringen mangler after-data."
            )

        change["target_id"] = project["id"]

        return change

    # ------------------------------------------------------------
    # Installationsændringer
    # ------------------------------------------------------------

    def _resolve_installation_field_change(
        self,
        change: dict[str, Any],
        project: dict[str, Any],
    ) -> dict[str, Any]:
        installation_id = (
            self._resolve_installation_id(
                change,
                project,
            )
        )

        change["installation_id"] = (
            installation_id
        )

        change["target_id"] = installation_id

        return change

    # ------------------------------------------------------------
    # Brøndændringer
    # ------------------------------------------------------------

    def _resolve_manhole_field_change(
        self,
        change: dict[str, Any],
        project: dict[str, Any],
    ) -> dict[str, Any]:
        after = change.get("after")

        if not isinstance(after, dict):
            raise ValueError(
                "Brøndændringen mangler after-data."
            )

        manhole_no = str(
            change.get("manhole_no")
            or after.get("manhole_no")
            or ""
        ).strip()

        if not manhole_no:
            raise ValueError(
                "Brøndændringen mangler brøndnummer."
            )

        manhole = (
            self.technical_asset_repository
            .get_manhole_by_number(
                project["id"],
                manhole_no,
            )
        )

        change["manhole_no"] = (
            manhole["manhole_no"]
        )

        change["target_id"] = (
            manhole["manhole_no"]
        )

        change["metadata"] = {
            **deepcopy(
                change.get("metadata")
                or {}
            ),
            "resolved_manhole_id": (
                manhole["id"]
            ),
        }

        return change

    # ------------------------------------------------------------
    # Holdændringer
    # ------------------------------------------------------------

    def _resolve_task_assignment_change(
        self,
        change: dict[str, Any],
        project: dict[str, Any],
        teams: dict[str, Any],
    ) -> dict[str, Any]:
        installation_id = (
            self._resolve_installation_id(
                change,
                project,
            )
        )

        after = change.get("after")

        if not isinstance(after, dict):
            raise ValueError(
                "Holdændringen mangler after-data."
            )

        task_type = str(
            after.get("task_type") or ""
        ).strip()

        if not task_type:
            raise ValueError(
                "Holdændringen mangler opgavetype."
            )

        team_reference = (
            after.get("team_id")
            or after.get("team")
        )

        team_id = self._resolve_team_id(
            team_reference,
            teams,
        )

        self._validate_team_permission(
            team_id=team_id,
            task_type=task_type,
            teams=teams,
        )

        change["installation_id"] = (
            installation_id
        )

        change["target_id"] = (
            f"{installation_id}:{task_type}"
        )

        change["after"] = {
            **after,
            "task_type": task_type,
            "team_id": team_id,
        }

        change["metadata"] = {
            **deepcopy(
                change.get("metadata")
                or {}
            ),
            "resolved_team_reference": str(
                team_reference or ""
            ),
        }

        change["after"].pop(
            "team",
            None,
        )

        return change

    # ------------------------------------------------------------
    # Projektopslag
    # ------------------------------------------------------------

    def _load_projects(
        self,
    ) -> dict[str, dict[str, Any]]:
        projects = {}

        for project_info in (
            self.project_repository.list_projects()
        ):
            project_id = str(
                project_info.get("id") or ""
            ).strip()

            if not project_id:
                continue

            project = (
                self.project_repository.load_project(
                    project_id
                )
            )

            if project:
                projects[project_id] = project

        return projects

    def _resolve_project_id(
        self,
        reference: Any,
        projects: dict[str, dict[str, Any]],
    ) -> str:
        normalized = self._normalize_text(
            reference
        )

        if not normalized:
            raise ValueError(
                "Ændringen mangler projekt-id "
                "eller projektnavn."
            )

        exact_id_matches = [
            project_id
            for project_id in projects
            if self._normalize_text(
                project_id
            ) == normalized
        ]

        if len(exact_id_matches) == 1:
            return exact_id_matches[0]

        name_matches = []

        for project_id, project in projects.items():
            candidates = {
                self._normalize_text(
                    project.get("name")
                ),
                self._normalize_text(
                    project.get("city")
                ),
            }

            if normalized in candidates:
                name_matches.append(
                    project_id
                )

        if len(name_matches) == 1:
            return name_matches[0]

        if len(name_matches) > 1:
            raise ValueError(
                f"Projektbetegnelsen '{reference}' "
                "matcher flere projekter."
            )

        raise FileNotFoundError(
            f"Projektet '{reference}' findes ikke."
        )

    # ------------------------------------------------------------
    # Installationer
    # ------------------------------------------------------------

    def _resolve_installation_id(
        self,
        change: dict[str, Any],
        project: dict[str, Any],
    ) -> str:
        after = change.get("after")
        before = change.get("before")

        references = [
            change.get("installation_id"),
            change.get("target_id"),
        ]

        if isinstance(after, dict):
            references.append(
                after.get("installation_id")
            )

        if isinstance(before, dict):
            references.append(
                before.get("installation_id")
            )

        reference = None

        for value in references:
            normalized = str(
                value or ""
            ).strip()

            if normalized:
                reference = normalized
                break

        if not reference:
            raise ValueError(
                "Ændringen mangler installationsnummer."
            )

        if ":" in reference:
            reference = reference.split(
                ":",
                1,
            )[0]

        installation_ids = {
            str(
                installation.get("id")
            )
            for installation
            in project.get(
                "installations",
                [],
            )
        }

        if reference not in installation_ids:
            raise FileNotFoundError(
                f"Installation {reference} findes "
                f"ikke på projekt {project.get('id')}."
            )

        return reference

    # ------------------------------------------------------------
    # Hold
    # ------------------------------------------------------------

    def _load_teams(
        self,
    ) -> dict[str, Any]:
        return (
            self.team_repository.load_team_map()
        )

    def _resolve_team_id(
        self,
        reference: Any,
        teams: dict[str, Any],
    ) -> str:
        normalized = self._normalize_text(
            reference
        )

        if not normalized:
            raise ValueError(
                "Holdændringen mangler hold."
            )

        exact_id_matches = [
            team_id
            for team_id in teams
            if self._normalize_text(
                team_id
            ) == normalized
        ]

        if len(exact_id_matches) == 1:
            return exact_id_matches[0]

        name_matches = []

        for team_id, team in teams.items():
            team_name = getattr(
                team,
                "name",
                "",
            )

            if (
                self._normalize_text(
                    team_name
                )
                == normalized
            ):
                name_matches.append(
                    team_id
                )

        if len(name_matches) == 1:
            return name_matches[0]

        if len(name_matches) > 1:
            raise ValueError(
                f"Holdbetegnelsen '{reference}' "
                "matcher flere hold."
            )

        raise FileNotFoundError(
            f"Holdet '{reference}' findes ikke."
        )

    def _validate_team_permission(
        self,
        *,
        team_id: str,
        task_type: str,
        teams: dict[str, Any],
    ) -> None:
        team = teams.get(team_id)

        if team is None:
            raise FileNotFoundError(
                f"Holdet '{team_id}' findes ikke."
            )

        allowed_task_types = getattr(
            team,
            "task_types",
            None,
        )

        if allowed_task_types is None:
            return

        normalized_allowed = {
            str(value).strip()
            for value in allowed_task_types
        }

        if task_type not in normalized_allowed:
            raise ValueError(
                f"Holdet '{team_id}' må ikke udføre "
                f"opgaven '{task_type}'."
            )

    # ------------------------------------------------------------
    # Tekstnormalisering
    # ------------------------------------------------------------

    def _normalize_text(
        self,
        value: Any,
    ) -> str:
        return (
            str(value or "")
            .strip()
            .casefold()
            .replace("_", " ")
            .replace("-", " ")
        )


scenario_change_resolver = (
    ScenarioChangeResolver()
)


def resolve_changes(
    changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Praktisk funktionsindgang til resolveren.
    """

    return (
        scenario_change_resolver.resolve_changes(
            changes
        )
    )
