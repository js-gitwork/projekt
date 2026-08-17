from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Any

from projektstyring.backend.project_planner import (
    generate_plan_for_project,
)
from projektstyring.backend.project_repository import (
    ProjectRepository,
)


project_repository = ProjectRepository()


def parse_date(
    value: Any,
) -> date | None:
    if not value:
        return None

    if isinstance(
        value,
        date,
    ):
        return value

    try:
        return date.fromisoformat(
            str(value)
        )
    except ValueError:
        return None


def summarize_plan(
    result,
) -> list[dict[str, Any]]:
    return [
        {
            "installation_id": (
                activity.installation_id
            ),
            "type": str(
                activity.type
            ),
            "team": activity.hold,
            "start": (
                str(activity.start_dato)
                if activity.start_dato
                else None
            ),
            "end": (
                str(activity.slut_dato)
                if activity.slut_dato
                else None
            ),
        }
        for activity in result.activities
    ]


def shift_installation_dates(
    project: dict[str, Any],
    day_delta: int,
) -> dict[str, Any]:
    shifted_project = deepcopy(
        project
    )

    for installation in (
        shifted_project.get(
            "installations",
            [],
        )
    ):
        hoveddato = parse_date(
            installation.get(
                "hoveddato"
            )
        )

        if hoveddato is None:
            continue

        installation[
            "hoveddato"
        ] = (
            hoveddato
            + timedelta(
                days=day_delta
            )
        ).isoformat()

    return shifted_project


def build_portfolio_plan(
    overrides: dict[
        str,
        dict[str, Any],
    ]
    | None = None,
) -> dict[
    str,
    list[dict[str, Any]],
]:
    overrides = (
        overrides
        or {}
    )

    plans = {}

    for project_info in (
        project_repository.list_projects()
    ):
        project_id = str(
            project_info.get("id")
            or ""
        ).strip()

        if not project_id:
            continue

        project = (
            overrides.get(
                project_id
            )
        )

        if project is None:
            project = (
                project_repository.load_project(
                    project_id
                )
            )

        result = (
            generate_plan_for_project(
                project
            )
        )

        plans[
            project_id
        ] = summarize_plan(
            result
        )

    return plans
