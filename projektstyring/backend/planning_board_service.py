from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from projektstyring.backend.planning_scenario_service import (
    PlanningScenarioService,
)
from projektstyring.backend.project_planner import (
    generate_plan_for_project,
)
from projektstyring.backend.project_repository import (
    ProjectRepository,
)
from projektstyring.backend.repositories.team_repository import (
    TeamRepository,
)


class PlanningBoardService:
    """
    Bygger en stabil datakontrakt til planlægningsarbejdsfladen.

    Arbejdsfladen kan vise enten:

    - den gældende produktionsplan
    - den aktive revision i et planlægningsscenarie

    Servicen ændrer ingen projekt- eller scenariedata.
    """

    def __init__(
        self,
        *,
        project_repository: ProjectRepository | None = None,
        team_repository: TeamRepository | None = None,
        scenario_service: PlanningScenarioService | None = None,
    ):
        self.project_repository = (
            project_repository
            or ProjectRepository()
        )

        self.team_repository = (
            team_repository
            or TeamRepository()
        )

        self.scenario_service = (
            scenario_service
            or PlanningScenarioService()
        )

    # ------------------------------------------------------------
    # Offentlig indgang
    # ------------------------------------------------------------

    def build_board(
        self,
        *,
        year: int,
        week: int,
        scenario_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Bygger en ugeplan for den ønskede ISO-uge.

        Hvis scenario_id er angivet, bruges scenariets aktive revision.
        Ellers bruges de gældende projekter i databasen.
        """

        period = self._build_period(
            year=year,
            week=week,
        )

        teams = self._load_teams()

        if scenario_id:
            source_data = self._load_scenario_source(
                scenario_id
            )
        else:
            source_data = self._load_production_source()

        activities = self._filter_activities_to_period(
            source_data["activities"],
            period=period,
        )

        return {
            "source": source_data["source"],
            "period": period,
            "teams": teams,
            "days": self._build_days(period),
            "activities": activities,
            "manual_entries": [],
            "conflicts": source_data["conflicts"],
            "warnings": source_data["warnings"],
            "unplanned_work": source_data["unplanned_work"],
        }

    # ------------------------------------------------------------
    # Periode
    # ------------------------------------------------------------

    def _build_period(
        self,
        *,
        year: int,
        week: int,
    ) -> dict[str, Any]:
        try:
            monday = date.fromisocalendar(
                int(year),
                int(week),
                1,
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Ugyldig ISO-uge: år={year}, uge={week}."
            ) from error

        sunday = monday + timedelta(days=6)

        return {
            "year": monday.isocalendar().year,
            "week": monday.isocalendar().week,
            "start_date": monday.isoformat(),
            "end_date": sunday.isoformat(),
        }

    def _build_days(
        self,
        period: dict[str, Any],
    ) -> list[dict[str, Any]]:
        start_date = date.fromisoformat(
            period["start_date"]
        )

        day_names = [
            "Mandag",
            "Tirsdag",
            "Onsdag",
            "Torsdag",
            "Fredag",
            "Lørdag",
            "Søndag",
        ]

        return [
            {
                "date": (
                    start_date
                    + timedelta(days=offset)
                ).isoformat(),
                "name": day_names[offset],
                "weekday": offset + 1,
                "is_weekend": offset >= 5,
            }
            for offset in range(7)
        ]

    # ------------------------------------------------------------
    # Hold
    # ------------------------------------------------------------

    def _load_teams(
        self,
    ) -> list[dict[str, Any]]:
        team_map = (
            self.team_repository.load_team_map()
        )

        teams = []

        for sequence, (
            team_id,
            team,
        ) in enumerate(
            team_map.items(),
            start=1,
        ):
            task_types = (
                getattr(
                    team,
                    "task_types",
                    [],
                )
                or []
            )

            teams.append(
                {
                    "id": str(team_id),
                    "name": str(
                        getattr(
                            team,
                            "name",
                            team_id,
                        )
                    ),
                    "task_types": [
                        str(task_type)
                        for task_type in task_types
                    ],
                    "sequence": sequence,
                    "visible": True,
                    # Personerne bliver senere hentet fra
                    # et særskilt bemandingslag.
                    "members": [],
                }
            )

        return teams

    # ------------------------------------------------------------
    # Produktionsplan
    # ------------------------------------------------------------

    def _load_production_source(
        self,
    ) -> dict[str, Any]:
        activities = []
        conflicts = []
        warnings = []
        unplanned_work = []

        projects = (
            self.project_repository.load_all_projects()
        )

        included_projects = []

        for project in projects:
            if project.get("status") not in {
                "upcoming",
                "active",
            }:
                continue

            project_id = str(
                project.get("id") or ""
            )

            if not project_id:
                continue

            included_projects.append(
                project_id
            )

            result = generate_plan_for_project(
                project
            )

            activities.extend(
                self._serialize_planned_activity(
                    activity,
                    project=project,
                    sequence=len(activities) + 1,
                )
                for activity in result.activities
            )

            warnings.extend(
                self._serialize_value(warning)
                for warning in (
                    result.warnings or []
                )
            )

            unplanned_work.extend(
                {
                    "project_id": project_id,
                    **self._serialize_value(item),
                }
                for item in (
                    result.rest_work or []
                )
            )

        return {
            "source": {
                "type": "production",
                "scenario_id": None,
                "revision_number": None,
                "project_ids": included_projects,
            },
            "activities": activities,
            "conflicts": conflicts,
            "warnings": warnings,
            "unplanned_work": unplanned_work,
        }

    # ------------------------------------------------------------
    # Scenarieplan
    # ------------------------------------------------------------

    def _load_scenario_source(
        self,
        scenario_id: str,
    ) -> dict[str, Any]:
        scenario = self.scenario_service.get_scenario(
            scenario_id
        )

        revision = (
            scenario.get("active_revision")
            or {}
        )

        raw_activities = (
            revision.get("activities")
            or []
        )

        activities = [
            self._serialize_scenario_activity(
                activity,
                sequence=sequence,
            )
            for sequence, activity in enumerate(
                raw_activities,
                start=1,
            )
        ]

        project_ids = self._scenario_project_ids(
            scenario
        )

        return {
            "source": {
                "type": "scenario",
                "scenario_id": scenario_id,
                "revision_number": revision.get(
                    "revision_number"
                ),
                "scenario_status": scenario.get(
                    "status"
                ),
                "project_ids": project_ids,
            },
            "activities": activities,
            "conflicts": (
                revision.get("conflicts")
                or []
            ),
            "warnings": (
                revision.get("warnings")
                or []
            ),
            "unplanned_work": (
                revision.get("unplanned_work")
                or revision.get("rest_work")
                or []
            ),
        }

    def _scenario_project_ids(
        self,
        scenario: dict[str, Any],
    ) -> list[str]:
        result = []

        for project in scenario.get(
            "projects",
            [],
        ):
            if isinstance(project, dict):
                project_id = (
                    project.get("project_id")
                    or project.get("id")
                )
            else:
                project_id = project

            normalized = str(
                project_id or ""
            ).strip()

            if normalized and normalized not in result:
                result.append(normalized)

        if result:
            return result

        revision = (
            scenario.get("active_revision")
            or {}
        )

        for activity in revision.get(
            "activities",
            [],
        ):
            project_id = str(
                activity.get("project_id")
                or ""
            ).strip()

            if project_id and project_id not in result:
                result.append(project_id)

        return result

    # ------------------------------------------------------------
    # Aktiviteter
    # ------------------------------------------------------------

    def _serialize_planned_activity(
        self,
        activity: Any,
        *,
        project: dict[str, Any],
        sequence: int,
    ) -> dict[str, Any]:
        project_id = str(
            project.get("id") or ""
        )

        installation_id = str(
            getattr(
                activity,
                "installation_id",
                "",
            )
        )

        task_type = str(
            getattr(
                activity,
                "type",
                "",
            )
        )

        team_id = str(
            getattr(
                activity,
                "hold",
                "",
            )
            or ""
        )

        start_date = self._date_string(
            getattr(
                activity,
                "start_dato",
                None,
            )
        )

        end_date = self._date_string(
            getattr(
                activity,
                "slut_dato",
                None,
            )
        )

        return {
            "activity_id": self._activity_id(
                project_id=project_id,
                installation_id=installation_id,
                task_type=task_type,
            ),
            "project_id": project_id,
            "project_name": str(
                project.get("name") or ""
            ),
            "project_city": str(
                project.get("city") or ""
            ),
            "installation_id": installation_id,
            "task_type": task_type,
            "team_id": team_id,
            "start_date": start_date,
            "end_date": end_date,
            "sequence": sequence,
            "locked": False,
            "lock_reason": "",
            "change_status": "unchanged",
            "status": str(
                getattr(
                    activity,
                    "status",
                    "planned",
                )
                or "planned"
            ),
            "quantities": {
                "stik": getattr(
                    activity,
                    "antal_stik",
                    0,
                ),
                "broende": getattr(
                    activity,
                    "antal_brønde",
                    0,
                ),
                "hovedledning_meter": getattr(
                    activity,
                    "hovedledning_meter",
                    0,
                ),
            },
            "notes": "",
            "metadata": {},
        }

    def _serialize_scenario_activity(
        self,
        activity: dict[str, Any],
        *,
        sequence: int,
    ) -> dict[str, Any]:
        project_id = str(
            activity.get("project_id")
            or ""
        )

        installation_id = str(
            activity.get("installation_no")
            or activity.get("installation_id")
            or ""
        )

        task_type = str(
            activity.get("task_type")
            or activity.get("type")
            or ""
        )

        start_date = self._date_string(
            activity.get("proposed_start")
            or activity.get("start_date")
            or activity.get("start")
            or activity.get("current_start")
        )

        end_date = self._date_string(
            activity.get("proposed_end")
            or activity.get("end_date")
            or activity.get("end")
            or activity.get("current_end")
        )

        team_id = str(
            activity.get("team_id")
            or activity.get("team")
            or ""
        )

        return {
            "activity_id": (
                activity.get("activity_id")
                or self._activity_id(
                    project_id=project_id,
                    installation_id=installation_id,
                    task_type=task_type,
                )
            ),
            "scenario_activity_id": activity.get(
                "id"
            ),
            "project_id": project_id,
            "project_name": str(
                activity.get("project_name")
                or ""
            ),
            "project_city": str(
                activity.get("project_city")
                or activity.get("city")
                or ""
            ),
            "installation_id": installation_id,
            "task_type": task_type,
            "team_id": team_id,
            "start_date": start_date,
            "end_date": end_date,
            "sequence": (
                activity.get("sequence")
                or sequence
            ),
            "locked": bool(
                activity.get("is_locked")
                or activity.get("locked")
            ),
            "lock_reason": str(
                activity.get("lock_reason")
                or ""
            ),
            "change_status": str(
                activity.get("change_status")
                or "unchanged"
            ),
            "status": str(
                activity.get("status")
                or "planned"
            ),
            "quantities": (
                activity.get("quantity")
                or activity.get("quantities")
                or {}
            ),
            "notes": str(
                activity.get("notes")
                or ""
            ),
            "metadata": (
                activity.get("metadata")
                or {}
            ),
        }

    def _activity_id(
        self,
        *,
        project_id: str,
        installation_id: str,
        task_type: str,
    ) -> str:
        return (
            f"{project_id}:"
            f"{installation_id}:"
            f"{task_type}"
        )

    # ------------------------------------------------------------
    # Ugefiltrering
    # ------------------------------------------------------------

    def _filter_activities_to_period(
        self,
        activities: list[dict[str, Any]],
        *,
        period: dict[str, Any],
    ) -> list[dict[str, Any]]:
        period_start = date.fromisoformat(
            period["start_date"]
        )

        period_end = date.fromisoformat(
            period["end_date"]
        )

        result = []

        for activity in activities:
            start_date = self._parse_date(
                activity.get("start_date")
            )

            end_date = self._parse_date(
                activity.get("end_date")
            )

            if start_date is None:
                continue

            if end_date is None:
                end_date = start_date

            if end_date < period_start:
                continue

            if start_date > period_end:
                continue

            result.append(activity)

        return sorted(
            result,
            key=lambda item: (
                item.get("start_date") or "",
                item.get("team_id") or "",
                item.get("sequence") or 0,
            ),
        )

    # ------------------------------------------------------------
    # Værdier
    # ------------------------------------------------------------

    def _parse_date(
        self,
        value: Any,
    ) -> date | None:
        if value in {
            None,
            "",
        }:
            return None

        if isinstance(value, date):
            return value

        try:
            return date.fromisoformat(
                str(value)
            )
        except ValueError:
            return None

    def _date_string(
        self,
        value: Any,
    ) -> str | None:
        parsed = self._parse_date(
            value
        )

        return (
            parsed.isoformat()
            if parsed
            else None
        )

    def _serialize_value(
        self,
        value: Any,
    ) -> Any:
        if isinstance(value, date):
            return value.isoformat()

        if isinstance(value, dict):
            return {
                str(key): self._serialize_value(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                self._serialize_value(item)
                for item in value
            ]

        if hasattr(value, "__dict__"):
            return {
                key: self._serialize_value(item)
                for key, item in vars(value).items()
                if not key.startswith("_")
            }

        return value


planning_board_service = PlanningBoardService()


def build_planning_board(
    *,
    year: int,
    week: int,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """
    Praktisk funktionsindgang til planlægningsarbejdsfladen.
    """

    return planning_board_service.build_board(
        year=year,
        week=week,
        scenario_id=scenario_id,
    )
