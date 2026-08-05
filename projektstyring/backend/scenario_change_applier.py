from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from projektstyring.backend.conflict_analyzer import (
    find_team_conflicts,
)
from projektstyring.backend.decision_engine import (
    build_portfolio_plan,
    shift_installation_dates,
    summarize_plan,
)
from projektstyring.backend.planning_scenario_service import (
    PlanningScenarioService,
)
from projektstyring.backend.project_planner import (
    generate_plan_for_project,
)


class ScenarioChangeApplier:
    """
    Anvender et valideret ændringssæt på et planlægningsscenarie.

    Klassen er generisk. Den er ikke bundet til flytning af projektstart.

    Arbejdsgangen er altid:

    1. Hent den aktive scenarierevision.
    2. Kopiér revisionens projektdata.
    3. Anvend én eller flere strukturerede ændringer.
    4. Beregn planer før og efter.
    5. Beregn konflikter i den samlede projektportefølje.
    6. Opret en ny, uforanderlig scenarierevision.

    De virkelige projekter ændres ikke.
    Der oprettes heller ingen snapshots på dette tidspunkt.
    """

    PROJECT_FIELDS = {
        "name",
        "customer",
        "city",
        "start_date",
        "planned_completion_date",
        "status",
        "notes",
    }

    INSTALLATION_FIELDS = {
        "active",
        "hoveddato",
        "expected_stik",
        "active_stik",
        "langhatte",
        "korthatte_extra",
        "broende",
        "hovedledning_meter",
        "notes",
    }

    SUPPORTED_CHANGE_TYPES = {
        "project_field_change",
        "installation_field_change",
        "task_assignment_change",
    }

    def __init__(
        self,
        *,
        scenario_service: PlanningScenarioService | None = None,
    ):
        self.scenario_service = (
            scenario_service
            or PlanningScenarioService()
        )

    # ------------------------------------------------------------
    # Offentlig indgang
    # ------------------------------------------------------------

    def apply_changes(
        self,
        *,
        scenario_id: str,
        changes: list[dict[str, Any]],
        user_message: str,
        reason: str = "",
        ai_summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Anvender ét samlet ændringssæt og opretter en ny revision.

        Flere ændringer i samme brugerbesked behandles samlet. Det gør
        det muligt at ændre flere projekter, installationer og hold i
        samme scenarie og derefter se den samlede konsekvens.
        """

        if not isinstance(changes, list) or not changes:
            raise ValueError(
                "Der skal angives mindst én ændring."
            )

        scenario = self.scenario_service.get_scenario(
            scenario_id
        )

        self._require_editable_scenario(scenario)

        active_revision = scenario.get(
            "active_revision"
        )

        if active_revision is None:
            raise ValueError(
                "Scenariet har ingen aktiv revision."
            )

        before_projects = self._load_revision_projects(
            scenario,
            active_revision,
        )

        after_projects = deepcopy(before_projects)

        normalized_changes = []

        for sequence, change in enumerate(
            changes,
            start=1,
        ):
            normalized_change = self._apply_change(
                projects=after_projects,
                change=change,
                sequence=sequence,
            )

            normalized_changes.append(
                normalized_change
            )

        before_plans = self._build_project_plans(
            before_projects
        )

        after_plans = self._build_project_plans(
            after_projects
        )

        scenario_activities = (
            self._build_scenario_activities(
                before_plans=before_plans,
                after_plans=after_plans,
            )
        )

        portfolio_after = build_portfolio_plan(
            overrides={
                project_id: project
                for project_id, project
                in after_projects.items()
            }
        )

        conflicts = find_team_conflicts(
            portfolio_after
        )

        warnings = self._collect_warnings(
            after_projects
        )

        calculated_result = self._make_json_safe(
            {
                "projects": [
                    deepcopy(project)
                    for project in after_projects.values()
                ],
                "plans": deepcopy(after_plans),
                "activities": deepcopy(
                    scenario_activities
                ),
                "conflicts": deepcopy(conflicts),
            }
        )

        if not ai_summary:
            ai_summary = self._build_summary(
                normalized_changes
            )

        return self.scenario_service.create_revision(
            scenario_id=scenario_id,
            user_message=user_message,
            reason=reason,
            ai_summary=ai_summary,
            calculated_result=calculated_result,
            activities=scenario_activities,
            changes=normalized_changes,
            conflicts=conflicts,
            warnings=warnings,
            constraints=[],
            metadata={
                **deepcopy(metadata or {}),
                "change_count": len(
                    normalized_changes
                ),
                "source_revision": (
                    active_revision.get(
                        "revision_number"
                    )
                ),
            },
        )

    # ------------------------------------------------------------
    # Ændringsrouting
    # ------------------------------------------------------------

    def _apply_change(
        self,
        *,
        projects: dict[str, dict[str, Any]],
        change: dict[str, Any],
        sequence: int,
    ) -> dict[str, Any]:
        """
        Validerer og anvender én struktureret ændring.
        """

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

        project_id = str(
            change.get("project_id") or ""
        ).strip()

        if not project_id:
            raise ValueError(
                f"Ændring {sequence} mangler project_id."
            )

        project = projects.get(project_id)

        if project is None:
            raise ValueError(
                f"Projektet '{project_id}' er ikke "
                "en del af scenariet."
            )

        if change_type == "project_field_change":
            return self._apply_project_field_change(
                project=project,
                change=change,
                sequence=sequence,
            )

        if change_type == "installation_field_change":
            return self._apply_installation_field_change(
                project=project,
                change=change,
                sequence=sequence,
            )

        if change_type == "task_assignment_change":
            return self._apply_task_assignment_change(
                project=project,
                change=change,
                sequence=sequence,
            )

        raise ValueError(
            f"Ændringstypen '{change_type}' "
            "kunne ikke behandles."
        )

    # ------------------------------------------------------------
    # Projektfelter
    # ------------------------------------------------------------

    def _apply_project_field_change(
        self,
        *,
        project: dict[str, Any],
        change: dict[str, Any],
        sequence: int,
    ) -> dict[str, Any]:
        """
        Ændrer ét tilladt felt på et projekt.

        Ved ændring af start_date forskydes installationernes hoveddatoer
        som standard med samme antal dage. Det kan fravælges eksplicit
        med options.shift_installation_dates = False.
        """

        field, new_value = self._extract_field_change(
            change
        )

        if field not in self.PROJECT_FIELDS:
            raise ValueError(
                f"Projektfeltet '{field}' må ikke ændres "
                "gennem et planlægningsscenarie."
            )

        before_value = deepcopy(
            project.get(field)
        )

        options = change.get("options")

        if not isinstance(options, dict):
            options = {}

        if field == "start_date":
            new_date = self._parse_required_date(
                new_value,
                field_name="start_date",
            )

            old_date = self._parse_optional_date(
                before_value
            )

            shift_dates = options.get(
                "shift_installation_dates",
                True,
            )

            project[field] = new_date.isoformat()

            if old_date and shift_dates:
                day_delta = (
                    new_date - old_date
                ).days

                shift_installation_dates(
                    project,
                    day_delta,
                )
            else:
                day_delta = 0

        else:
            project[field] = deepcopy(
                new_value
            )
            day_delta = None

        normalized = self._base_change(
            sequence=sequence,
            change=change,
            project_id=project["id"],
            change_type="project_field_change",
            target_type="project",
            target_id=project["id"],
        )

        normalized["before"] = {
            "field": field,
            "value": before_value,
        }

        normalized["after"] = {
            "field": field,
            "value": deepcopy(
                project.get(field)
            ),
        }

        normalized["metadata"] = {
            **normalized["metadata"],
            "field": field,
        }

        if day_delta is not None:
            normalized["metadata"][
                "day_delta"
            ] = day_delta

            normalized["metadata"][
                "shifted_installation_dates"
            ] = bool(
                options.get(
                    "shift_installation_dates",
                    True,
                )
                and old_date
            )

        return normalized

    # ------------------------------------------------------------
    # Installationsfelter
    # ------------------------------------------------------------

    def _apply_installation_field_change(
        self,
        *,
        project: dict[str, Any],
        change: dict[str, Any],
        sequence: int,
    ) -> dict[str, Any]:
        """
        Ændrer ét tilladt felt på én installation.
        """

        installation_id = self._extract_installation_id(
            change
        )

        installation = self._find_installation(
            project,
            installation_id,
        )

        field, new_value = self._extract_field_change(
            change
        )

        if field not in self.INSTALLATION_FIELDS:
            raise ValueError(
                f"Installationsfeltet '{field}' må ikke "
                "ændres gennem et planlægningsscenarie."
            )

        before_value = deepcopy(
            installation.get(field)
        )

        if field == "hoveddato":
            if new_value in {None, ""}:
                normalized_value = ""
            else:
                normalized_value = (
                    self._parse_required_date(
                        new_value,
                        field_name="hoveddato",
                    ).isoformat()
                )

            installation[field] = normalized_value
        else:
            installation[field] = deepcopy(
                new_value
            )

        normalized = self._base_change(
            sequence=sequence,
            change=change,
            project_id=project["id"],
            change_type=(
                "installation_field_change"
            ),
            target_type="installation",
            target_id=installation_id,
        )

        normalized["before"] = {
            "installation_id": installation_id,
            "field": field,
            "value": before_value,
        }

        normalized["after"] = {
            "installation_id": installation_id,
            "field": field,
            "value": deepcopy(
                installation.get(field)
            ),
        }

        normalized["metadata"] = {
            **normalized["metadata"],
            "field": field,
        }

        return normalized

    # ------------------------------------------------------------
    # Opgavefordeling
    # ------------------------------------------------------------

    def _apply_task_assignment_change(
        self,
        *,
        project: dict[str, Any],
        change: dict[str, Any],
        sequence: int,
    ) -> dict[str, Any]:
        """
        Flytter en installations opgave til et andet hold.

        Eksempel:
        installation 12, opgave stik, fra stik2 til stik1.
        """

        installation_id = self._extract_installation_id(
            change
        )

        self._find_installation(
            project,
            installation_id,
        )

        after = change.get("after")

        if not isinstance(after, dict):
            raise ValueError(
                "task_assignment_change mangler after-data."
            )

        task_type = str(
            after.get("task_type")
            or change.get("task_type")
            or ""
        ).strip()

        new_team_id = str(
            after.get("team_id")
            or after.get("team")
            or ""
        ).strip()

        if not task_type:
            raise ValueError(
                "Opgavetypen mangler i holdændringen."
            )

        if not new_team_id:
            raise ValueError(
                "Det nye hold mangler i holdændringen."
            )

        assignments = project.setdefault(
            "task_assignments",
            {},
        )

        task_assignments = assignments.setdefault(
            task_type,
            [],
        )

        old_team_id = self._find_assigned_team(
            task_assignments,
            installation_id,
        )

        self._remove_installation_assignment(
            task_assignments,
            installation_id,
        )

        self._add_installation_assignment(
            task_assignments,
            installation_id=installation_id,
            team_id=new_team_id,
        )

        normalized = self._base_change(
            sequence=sequence,
            change=change,
            project_id=project["id"],
            change_type="task_assignment_change",
            target_type="installation_task",
            target_id=(
                f"{installation_id}:{task_type}"
            ),
        )

        normalized["before"] = {
            "installation_id": installation_id,
            "task_type": task_type,
            "team_id": old_team_id,
        }

        normalized["after"] = {
            "installation_id": installation_id,
            "task_type": task_type,
            "team_id": new_team_id,
        }

        return normalized

    # ------------------------------------------------------------
    # Planberegning
    # ------------------------------------------------------------

    def _build_project_plans(
        self,
        projects: dict[str, dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Beregner hvert scenarieprojekts plan med den eksisterende motor.
        """

        plans = {}

        for project_id, project in projects.items():
            result = generate_plan_for_project(
                deepcopy(project)
            )

            plans[project_id] = summarize_plan(
                result
            )

        return plans

    def _build_scenario_activities(
        self,
        *,
        before_plans: dict[
            str,
            list[dict[str, Any]],
        ],
        after_plans: dict[
            str,
            list[dict[str, Any]],
        ],
    ) -> list[dict[str, Any]]:
        """
        Bygger den permanente aktivitetskontrakt til scenarierevisionen.

        Identiteten er projekt, installation og opgavetype. Holdet indgår
        ikke i nøglen, fordi et holdskifte ellers fejlagtigt ville ligne
        én fjernet og én ny aktivitet.
        """

        activities = []

        project_ids = sorted(
            set(before_plans)
            | set(after_plans)
        )

        for project_id in project_ids:
            before_index = self._index_plan(
                before_plans.get(
                    project_id,
                    [],
                )
            )

            after_index = self._index_plan(
                after_plans.get(
                    project_id,
                    [],
                )
            )

            keys = sorted(
                set(before_index)
                | set(after_index)
            )

            for key in keys:
                before = before_index.get(key)
                after = after_index.get(key)

                change_status = (
                    self._activity_change_status(
                        before,
                        after,
                    )
                )

                source = after or before or {}

                activities.append(
                    {
                        "project_id": project_id,
                        "installation_no": str(
                            source.get(
                                "installation_id",
                                "",
                            )
                        ),
                        "task_type": str(
                            source.get(
                                "type",
                                "",
                            )
                        ),
                        "team_id": (
                            after.get("team")
                            if after
                            else before.get("team")
                            if before
                            else None
                        ),
                        "current_start": (
                            self._parse_optional_date(
                                before.get("start")
                            )
                            if before
                            else None
                        ),
                        "current_end": (
                            self._parse_optional_date(
                                before.get("end")
                            )
                            if before
                            else None
                        ),
                        "proposed_start": (
                            self._parse_optional_date(
                                after.get("start")
                            )
                            if after
                            else None
                        ),
                        "proposed_end": (
                            self._parse_optional_date(
                                after.get("end")
                            )
                            if after
                            else None
                        ),
                        "change_status": change_status,
                        "status": None,
                        "quantity": {},
                        "notes": "",
                        "is_locked": False,
                        "lock_reason": "",
                        "metadata": {
                            "current_team_id": (
                                before.get("team")
                                if before
                                else None
                            ),
                            "proposed_team_id": (
                                after.get("team")
                                if after
                                else None
                            ),
                        },
                    }
                )

        return activities

    def _index_plan(
        self,
        plan: list[dict[str, Any]],
    ) -> dict[
        tuple[str, str],
        dict[str, Any],
    ]:
        return {
            (
                str(
                    activity.get(
                        "installation_id"
                    )
                ),
                str(
                    activity.get("type")
                ),
            ): activity
            for activity in plan
        }

    def _activity_change_status(
        self,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> str:
        if before is None and after is not None:
            return "added"

        if before is not None and after is None:
            return "removed"

        if not before or not after:
            return "unchanged"

        if before.get("team") != after.get("team"):
            return "reassigned"

        if (
            before.get("start")
            != after.get("start")
            or before.get("end")
            != after.get("end")
        ):
            return "moved"

        return "unchanged"

    def _collect_warnings(
        self,
        projects: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Samler planmotorens advarsler og restarbejde.
        """

        warnings = []

        for project_id, project in projects.items():
            result = generate_plan_for_project(
                deepcopy(project)
            )

            for warning in result.warnings:
                warnings.append(
                    {
                        "project_id": project_id,
                        "type": "warning",
                        "installation_id": getattr(
                            warning,
                            "installation_id",
                            None,
                        ),
                        "message": getattr(
                            warning,
                            "message",
                            str(warning),
                        ),
                        "severity": getattr(
                            warning,
                            "severity",
                            "warning",
                        ),
                    }
                )

            for item in result.rest_work:
                warnings.append(
                    {
                        "project_id": project_id,
                        "type": "rest_work",
                        "installation_id": getattr(
                            item,
                            "installation_id",
                            None,
                        ),
                        "task_type": getattr(
                            item,
                            "task_type",
                            None,
                        ),
                        "message": getattr(
                            item,
                            "reason",
                            "Ikke planlagt arbejde",
                        ),
                    }
                )

        return warnings

    # ------------------------------------------------------------
    # Scenarietilstand
    # ------------------------------------------------------------

    def _load_revision_projects(
        self,
        scenario: dict[str, Any],
        active_revision: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """
        Henter den kumulative projekttilstand fra den aktive revision.

        Hvis revisionen ikke har projektdata, bruges scenariets fastlåste
        base_project_state.
        """

        calculated_result = (
            active_revision.get(
                "calculated_result"
            )
            or {}
        )

        revision_projects = (
            calculated_result.get("projects")
        )

        if isinstance(revision_projects, list):
            projects = {
                str(project["id"]): deepcopy(
                    project
                )
                for project in revision_projects
                if isinstance(project, dict)
                and project.get("id")
            }

            if projects:
                return projects

        return {
            str(item["project_id"]): deepcopy(
                item["base_project_state"]
            )
            for item in scenario.get(
                "projects",
                [],
            )
        }

    def _require_editable_scenario(
        self,
        scenario: dict[str, Any],
    ) -> None:
        if scenario.get("status") in {
            "committed",
            "cancelled",
        }:
            raise ValueError(
                f"Scenariet har status "
                f"'{scenario.get('status')}' "
                "og kan ikke ændres."
            )

    # ------------------------------------------------------------
    # Hjælpefunktioner til ændringer
    # ------------------------------------------------------------

    def _extract_field_change(
        self,
        change: dict[str, Any],
    ) -> tuple[str, Any]:
        after = change.get("after")

        if not isinstance(after, dict):
            raise ValueError(
                "Feltændringen mangler after-data."
            )

        field = str(
            after.get("field")
            or change.get("field")
            or ""
        ).strip()

        if not field:
            raise ValueError(
                "Feltændringen mangler feltnavn."
            )

        if "value" in after:
            value = after["value"]
        elif field in after:
            value = after[field]
        else:
            raise ValueError(
                f"Feltændringen mangler en ny værdi "
                f"for '{field}'."
            )

        return field, value

    def _extract_installation_id(
        self,
        change: dict[str, Any],
    ) -> str:
        after = change.get("after")
        before = change.get("before")

        values = [
            change.get("installation_id"),
            change.get("target_id"),
        ]

        if isinstance(after, dict):
            values.append(
                after.get("installation_id")
            )

        if isinstance(before, dict):
            values.append(
                before.get("installation_id")
            )

        for value in values:
            normalized = str(
                value or ""
            ).strip()

            if normalized:
                if ":" in normalized:
                    normalized = normalized.split(
                        ":",
                        1,
                    )[0]

                return normalized

        raise ValueError(
            "Ændringen mangler installationsnummer."
        )

    def _find_installation(
        self,
        project: dict[str, Any],
        installation_id: str,
    ) -> dict[str, Any]:
        for installation in project.get(
            "installations",
            [],
        ):
            if str(
                installation.get("id")
            ) == str(installation_id):
                return installation

        raise FileNotFoundError(
            f"Installation {installation_id} findes "
            f"ikke på projekt {project.get('id')}."
        )

    def _find_assigned_team(
        self,
        assignments: list[dict[str, Any]],
        installation_id: str,
    ) -> str | None:
        for assignment in assignments:
            installation_ids = {
                str(value)
                for value in assignment.get(
                    "installations",
                    [],
                )
            }

            if installation_id in installation_ids:
                return assignment.get("team")

        return None

    def _remove_installation_assignment(
        self,
        assignments: list[dict[str, Any]],
        installation_id: str,
    ) -> None:
        empty_assignments = []

        for assignment in assignments:
            assignment["installations"] = [
                value
                for value in assignment.get(
                    "installations",
                    [],
                )
                if str(value)
                != str(installation_id)
            ]

            if not assignment["installations"]:
                empty_assignments.append(
                    assignment
                )

        for assignment in empty_assignments:
            assignments.remove(assignment)

    def _add_installation_assignment(
        self,
        assignments: list[dict[str, Any]],
        *,
        installation_id: str,
        team_id: str,
    ) -> None:
        for assignment in assignments:
            if assignment.get("team") == team_id:
                installation_ids = [
                    str(value)
                    for value in assignment.get(
                        "installations",
                        [],
                    )
                ]

                if (
                    installation_id
                    not in installation_ids
                ):
                    assignment.setdefault(
                        "installations",
                        [],
                    ).append(
                        installation_id
                    )

                return

        assignments.append(
            {
                "team": team_id,
                "installations": [
                    installation_id
                ],
            }
        )

    def _base_change(
        self,
        *,
        sequence: int,
        change: dict[str, Any],
        project_id: str,
        change_type: str,
        target_type: str,
        target_id: str | None,
    ) -> dict[str, Any]:
        return {
            "sequence": sequence,
            "project_id": project_id,
            "change_type": change_type,
            "target_type": target_type,
            "target_id": target_id,
            "status": "proposed",
            "reason": str(
                change.get("reason")
                or ""
            ),
            "before": None,
            "after": None,
            "metadata": deepcopy(
                change.get("metadata")
                or {}
            ),
        }

    def _build_summary(
        self,
        changes: list[dict[str, Any]],
    ) -> str:
        project_ids = sorted({
            change["project_id"]
            for change in changes
        })

        return (
            f"{len(changes)} foreslåede ændringer "
            f"på {len(project_ids)} projekter."
        )

    # ------------------------------------------------------------
    # Datoer
    # ------------------------------------------------------------

    def _make_json_safe(
        self,
        value: Any,
    ) -> Any:
        """
        Konverterer data til værdier, som kan gemmes i JSONB.

        Date- og datetime-objekter bruges fortsat direkte i tabellernes
        Date/DateTime-kolonner, men skal konverteres til ISO-strenge,
        når de også gemmes inde i calculated_result eller metadata.
        """

        if isinstance(value, date):
            return value.isoformat()

        if isinstance(value, dict):
            return {
                str(key): self._make_json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                self._make_json_safe(item)
                for item in value
            ]

        return value

    def _parse_optional_date(
        self,
        value: Any,
    ) -> date | None:
        if value in {None, ""}:
            return None

        if isinstance(value, date):
            return value

        try:
            return date.fromisoformat(
                str(value)
            )
        except ValueError:
            return None

    def _parse_required_date(
        self,
        value: Any,
        *,
        field_name: str,
    ) -> date:
        parsed = self._parse_optional_date(
            value
        )

        if parsed is None:
            raise ValueError(
                f"'{value}' er ikke en gyldig dato "
                f"for {field_name}. Brug YYYY-MM-DD."
            )

        return parsed


scenario_change_applier = ScenarioChangeApplier()


def apply_changes(
    *,
    scenario_id: str,
    changes: list[dict[str, Any]],
    user_message: str,
    reason: str = "",
    ai_summary: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Praktisk funktionsindgang til den generiske ændringsmotor.
    """

    return scenario_change_applier.apply_changes(
        scenario_id=scenario_id,
        changes=changes,
        user_message=user_message,
        reason=reason,
        ai_summary=ai_summary,
        metadata=metadata,
    )
