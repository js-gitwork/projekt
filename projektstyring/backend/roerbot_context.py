"""
Roerbot Context Builder
=======================

Henter de data, som AI-fortolkeren har efterspurgt.

Context Builder må:
- læse data gennem repositories og eksisterende motorer
- filtrere og sortere deterministisk
- samle data til rapportering

Context Builder må ikke:
- ændre databasen
- godkende beslutninger
- lade AI opfinde databaseforespørgsler
- udføre vilkårlig kode fra modeloutput
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Any

from projektstyring.backend.project_planner import (
    generate_plan_for_project,
)
from projektstyring.backend.project_repository import (
    ProjectRepository,
)
from projektstyring.backend.repositories.team_repository import (
    TeamRepository,
)
import re

project_repository = ProjectRepository()
team_repository = TeamRepository()


ALLOWED_FILTER_OPERATORS = {
    "equals",
    "not_equals",
    "in",
    "not_in",
    "contains",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "is_null",
    "is_not_null",
}


def value_of(
    item: Any,
    field: str,
    default: Any = None,
) -> Any:
    """
    Læser et felt fra enten dictionary eller objekt.
    """

    if isinstance(item, dict):
        return item.get(field, default)

    return getattr(item, field, default)


def serialize_value(
    value: Any,
) -> Any:
    """
    Konverterer almindelige modelværdier til JSON-egnede Python-data.
    """

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): serialize_value(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            serialize_value(item)
            for item in value
        ]

    if hasattr(value, "__dict__"):
        return {
            key: serialize_value(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }

    return value


def project_summary(
    project: Any,
) -> dict[str, Any]:
    """
    Returnerer projektets centrale felter i en ensartet struktur.
    """

    return {
        "id": str(value_of(project, "id", "")),
        "name": value_of(project, "name", ""),
        "customer": value_of(
            project,
            "customer",
            "",
        ),
        "city": value_of(project, "city", ""),
        "status": value_of(
            project,
            "status",
            "",
        ),
        "start_date": serialize_value(
            value_of(project, "start_date")
        ),
    }


def normalize_comparable(
    value: Any,
) -> Any:
    """
    Normaliserer værdier, før filtre sammenlignes.
    """

    if isinstance(value, str):
        return value.strip().lower()

    return value


def filter_matches(
    item: dict[str, Any],
    filter_data: dict[str, Any],
) -> bool:
    """
    Evaluerer ét godkendt filter mod ét dataelement.

    Der fortolkes aldrig Python-kode eller SQL fra AI-outputtet.
    """

    field = str(
        filter_data.get("field") or ""
    ).strip()

    operator = str(
        filter_data.get("operator") or "equals"
    ).strip()

    expected = filter_data.get("value")
    actual = item.get(field)

    if not field:
        return True

    if operator not in ALLOWED_FILTER_OPERATORS:
        return True

    if operator == "is_null":
        return actual is None

    if operator == "is_not_null":
        return actual is not None

    normalized_actual = normalize_comparable(
        actual
    )

    if isinstance(expected, list):
        normalized_expected = [
            normalize_comparable(value)
            for value in expected
        ]
    else:
        normalized_expected = normalize_comparable(
            expected
        )

    if operator == "equals":
        return normalized_actual == normalized_expected

    if operator == "not_equals":
        return normalized_actual != normalized_expected

    if operator == "in":
        if not isinstance(
            normalized_expected,
            list,
        ):
            return False

        return normalized_actual in normalized_expected

    if operator == "not_in":
        if not isinstance(
            normalized_expected,
            list,
        ):
            return True

        return normalized_actual not in normalized_expected

    if operator == "contains":
        if actual is None:
            return False

        return str(normalized_expected) in str(
            normalized_actual
        )

    try:
        if operator == "greater_than":
            return actual > expected

        if operator == "greater_than_or_equal":
            return actual >= expected

        if operator == "less_than":
            return actual < expected

        if operator == "less_than_or_equal":
            return actual <= expected

    except TypeError:
        return False

    return True


def apply_filters(
    items: list[dict[str, Any]],
    filters: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """
    Anvender alle filtre som en AND-kæde.
    """

    valid_filters = [
        filter_data
        for filter_data in filters or []
        if isinstance(filter_data, dict)
    ]

    if not valid_filters:
        return items

    return [
        item
        for item in items
        if all(
            filter_matches(
                item,
                filter_data,
            )
            for filter_data in valid_filters
        )
    ]


def apply_sort(
    items: list[dict[str, Any]],
    sort_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Sorterer et datasæt efter et tilladt felt.
    """

    if not isinstance(sort_data, dict):
        return items

    field = str(
        sort_data.get("field") or ""
    ).strip()

    if not field:
        return items

    descending = (
        str(
            sort_data.get("direction")
            or "ascending"
        ).lower()
        == "descending"
    )

    return sorted(
        items,
        key=lambda item: (
            item.get(field) is None,
            str(item.get(field) or "").lower(),
        ),
        reverse=descending,
    )


def apply_limit(
    items: list[dict[str, Any]],
    limit: Any,
) -> list[dict[str, Any]]:
    """
    Begrænser antallet af resultater uden at tillade negative værdier.
    """

    try:
        normalized_limit = int(limit)
    except (TypeError, ValueError):
        return items

    if normalized_limit <= 0:
        return []

    return items[:normalized_limit]


def requested_project_ids(
    interpretation: dict[str, Any],
) -> list[str]:
    """
    Finder projekt-id'er fra fortolkningens scope.
    """

    scope = interpretation.get("scope")

    if not isinstance(scope, dict):
        return []

    values = scope.get("project_ids")

    if not isinstance(values, list):
        return []

    return [
        str(value).strip()
        for value in values
        if str(value or "").strip()
    ]


def load_projects_resource() -> list[dict[str, Any]]:
    """
    Henter projektoversigten fra databasen.
    """

    return [
        project_summary(project)
        for project in (
            project_repository.list_projects()
        )
    ]


def load_project_resource(
    project_ids: list[str],
) -> list[dict[str, Any]]:
    """
    Henter komplette projekter fra databasen.
    """

    projects = []

    for project_id in project_ids:
        project = project_repository.load_project(
            project_id
        )

        if project:
            projects.append(
                deepcopy(project)
            )

    return projects


def relevant_projects(
    interpretation: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Henter de projekter, som øvrige ressourcer skal bygges ud fra.

    Uden eksplicit scope bruges alle projekter.
    """

    project_ids = requested_project_ids(
        interpretation
    )

    if project_ids:
        return load_project_resource(project_ids)

    summaries = load_projects_resource()
    projects = []

    for summary in summaries:
        project_id = summary.get("id")

        if not project_id:
            continue

        project = project_repository.load_project(
            project_id
        )

        if project:
            projects.append(project)

    return projects


def load_installations_resource(
    interpretation: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Samler installationer på tværs af de relevante projekter.
    """

    result = []

    for project in relevant_projects(
        interpretation
    ):
        for installation in project.get(
            "installations",
            [],
        ):
            result.append(
                {
                    "project_id": project.get("id"),
                    "project_name": project.get(
                        "name"
                    ),
                    **deepcopy(installation),
                }
            )

    return result


def load_progress_resource(
    interpretation: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Returnerer fremdriftsdata pr. installation.
    """

    result = []

    for installation in load_installations_resource(
        interpretation
    ):
        result.append(
            {
                "project_id": installation.get(
                    "project_id"
                ),
                "installation_id": str(
                    installation.get("id")
                ),
                "active": installation.get(
                    "active",
                    True,
                ),
                "expected_stik": installation.get(
                    "expected_stik",
                    0,
                ),
                "active_stik": installation.get(
                    "active_stik",
                    0,
                ),
                "opened_stik": installation.get(
                    "opened_stik",
                    0,
                ),
                "progress": deepcopy(
                    installation.get("progress")
                    or {}
                ),
            }
        )

    return result


def load_assignments_resource(
    interpretation: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Flader projekternes opgavefordeling ud til rapportering.
    """

    result = []

    for project in relevant_projects(
        interpretation
    ):
        assignments = (
            project.get("task_assignments")
            or {}
        )

        for task_type, groups in assignments.items():
            for assignment in groups:
                result.append(
                    {
                        "project_id": project.get(
                            "id"
                        ),
                        "task_type": task_type,
                        "team_id": assignment.get(
                            "team"
                        ),
                        "installation_ids": [
                            str(value)
                            for value in assignment.get(
                                "installations",
                                [],
                            )
                        ],
                    }
                )

    return result


def load_teams_resource() -> list[dict[str, Any]]:
    """
    Henter holdkortet fra databasen.
    """

    teams = team_repository.load_team_map()

    return [
        {
            "id": str(team_id),
            **serialize_value(team),
        }
        for team_id, team in teams.items()
    ]


def summarize_activity(
    project_id: str,
    activity: Any,
) -> dict[str, Any]:
    """
    Serialiserer en beregnet planaktivitet.
    """

    return {
        "project_id": project_id,
        "installation_id": str(
            value_of(
                activity,
                "installation_id",
                "",
            )
        ),
        "task_type": str(
            value_of(activity, "type", "")
        ),
        "team_id": value_of(
            activity,
            "hold",
        ),
        "start_date": serialize_value(
            value_of(
                activity,
                "start_dato",
            )
        ),
        "end_date": serialize_value(
            value_of(
                activity,
                "slut_dato",
            )
        ),
        "stik": value_of(
            activity,
            "antal_stik",
            0,
        ),
        "broende": value_of(
            activity,
            "antal_brønde",
            0,
        ),
        "hovedledning_meter": value_of(
            activity,
            "hovedledning_meter",
            0,
        ),
    }


def load_plan_resources(
    interpretation: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """
    Beregner planer med den eksisterende deterministiske planmotor.

    AI'en analyserer resultatet, men beregner ikke planen.
    """

    activities = []
    warnings = []
    rest_work = []

    for project in relevant_projects(
        interpretation
    ):
        project_id = str(
            project.get("id") or ""
        )

        result = generate_plan_for_project(
            project
        )

        activities.extend(
            summarize_activity(
                project_id,
                activity,
            )
            for activity in result.activities
        )

        warnings.extend(
            {
                "project_id": project_id,
                **serialize_value(warning),
            }
            for warning in result.warnings
        )

        rest_work.extend(
            {
                "project_id": project_id,
                **serialize_value(item),
            }
            for item in result.rest_work
        )

    return {
        "plan": activities,
        "conflicts": warnings,
        "rest_work": rest_work,
    }


def load_project_rules_resource(
    interpretation: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Samler godkendte projektregler fra de relevante projekter.
    """

    result = []

    for project in relevant_projects(
        interpretation
    ):
        for rule in project.get(
            "project_rules",
            [],
        ):
            result.append(
                {
                    "project_id": project.get("id"),
                    **deepcopy(rule),
                }
            )

    return result


def build_resource(
    resource: str,
    interpretation: dict[str, Any],
) -> Any:
    """
    Henter én kendt ressource.
    """

    if resource == "projects":
        return load_projects_resource()

    if resource == "project":
        return load_project_resource(
            requested_project_ids(
                interpretation
            )
        )

    if resource == "installations":
        return load_installations_resource(
            interpretation
        )

    if resource == "progress":
        return load_progress_resource(
            interpretation
        )

    if resource in {
        "tasks",
        "task_assignments",
    }:
        return load_assignments_resource(
            interpretation
        )

    if resource == "teams":
        return load_teams_resource()

    if resource in {
        "plan",
        "conflicts",
        "rest_work",
    }:
        return load_plan_resources(
            interpretation
        ).get(resource, [])

    if resource == "project_rules":
        return load_project_rules_resource(
            interpretation
        )

    # Disse ressourcer kobles på deres database-repositories i næste trin.
    if resource in {
        "calendars",
        "decisions",
        "snapshots",
        "changes",
    }:
        return []

    return []


def build_context(
    interpretation: dict[str, Any],
) -> dict[str, Any]:
    """
    Henter og filtrerer de data, AI-fortolkeren har bedt om.
    """

    context: dict[str, Any] = {
        "scope": deepcopy(
            interpretation.get("scope")
            or {}
        ),
        "resources": {},
    }

    requests = interpretation.get(
        "data_requests"
    )

    if not isinstance(requests, list):
        requests = []

    for request in requests:
        if not isinstance(request, dict):
            continue

        resource = str(
            request.get("resource") or ""
        ).strip()

        if not resource:
            continue

        data = build_resource(
            resource,
            interpretation,
        )

        if isinstance(data, list):
            data = apply_filters(
                data,
                request.get("filters"),
            )
            data = apply_sort(
                data,
                request.get("sort"),
            )
            data = apply_limit(
                data,
                request.get("limit"),
            )

        context["resources"][resource] = data

    return context
def build_interpreter_context(
    *,
    question: str = "",
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """
    Bygger en kompakt og faktabaseret kontekst til AI-fortolkeren.

    Konteksten gør det muligt at skelne mellem:
    - projekter og projektnavne
    - installationer
    - opgavetyper
    - hold og holdnavne
    - nuværende opgavefordeling

    Funktionen ændrer ingen data.
    """

    projects = []

    explicit_project_ids = {
        value.casefold()
        for value in extract_explicit_project_ids(
            question
        )
    }

    for project_info in project_repository.list_projects():
        project_id = str(
            project_info.get("id") or ""
        ).strip()

        if not project_id:
            continue

        if (
            explicit_project_ids
            and project_id.casefold()
            not in explicit_project_ids
        ):
            continue

        project = project_repository.load_project(
            project_id
        )

        if not project:
            continue

        installations = [
            {
                "id": str(
                    installation.get("id")
                ),
                "active": installation.get(
                    "active",
                    True,
                ),
            }
            for installation in project.get(
                "installations",
                [],
            )
        ]

        assignments = []

        for task_type, groups in (
            project.get("task_assignments")
            or {}
        ).items():
            for assignment in groups:
                assignments.append(
                    {
                        "task_type": str(task_type),
                        "team_id": assignment.get(
                            "team"
                        ),
                        "installation_ids": [
                            str(value)
                            for value
                            in assignment.get(
                                "installations",
                                [],
                            )
                        ],
                    }
                )

        projects.append(
            {
                "id": project_id,
                "name": project.get("name", ""),
                "city": project.get("city", ""),
                "status": project.get(
                    "status",
                    "",
                ),
                "installations": installations,
                "task_assignments": assignments,
            }
        )

    team_map = team_repository.load_team_map()

    teams = []

    for team_id, team in team_map.items():
        teams.append(
            {
                "id": str(team_id),
                "name": getattr(
                    team,
                    "name",
                    "",
                ),
                "task_types": [
                    str(value)
                    for value in (
                        getattr(
                            team,
                            "task_types",
                            [],
                        )
                        or []
                    )
                ],
            }
        )

    task_types = sorted({
        task_type
        for team in teams
        for task_type in team["task_types"]
    })

    return {
        "active_scenario": {
            "scenario_id": scenario_id,
        },
        "projects": projects,
        "teams": teams,
        "task_types": task_types,
    }

def extract_explicit_project_ids(
    question: str,
) -> list[str]:
    """
    Finder eksplicit angivne V-numre i brugerens besked.

    Dette fortolker ikke brugerens hensigt. Det bruges kun til at
    begrænse interpreterens kontekst til relevante projekter.
    """

    matches = re.findall(
        r"\bV[A-Za-z0-9_-]+\b",
        str(question or ""),
        flags=re.IGNORECASE,
    )

    result = []

    for match in matches:
        normalized = match.strip()

        if normalized not in result:
            result.append(normalized)

    return result