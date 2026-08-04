from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import (
    TaskType,
    Team,
    TeamCapacityRate,
    TeamTaskPermission,
    WorkCalendar,
)


DEFAULT_TEAM_FILE = Path(
    "projektstyring/data/teams.json"
)


def resolve_task_permissions(
    team_data: dict,
    valid_task_types: set[str],
) -> set[str]:
    permissions = {
        str(task_type)
        for task_type in team_data.get(
            "task_types",
            [],
        )
        if str(task_type) in valid_task_types
    }

    role = str(team_data.get("role") or "")

    # Cutter er en teknisk funktion og ikke en opgavetype.
    # Cutterhold kan anvendes til forarbejde og
    # stikforberedelse.
    if role == "cutter":
        permissions.update(
            {
                "forarbejde",
                "stikforberedelse",
            }
            & valid_task_types
        )

    return permissions


def capacity_definitions(
    team_data: dict,
    permissions: set[str],
) -> list[dict]:
    team_id = str(team_data["id"])
    role = str(team_data.get("role") or "")
    configured_capacity = float(
        team_data.get("capacity_per_day") or 0
    )

    definitions = []

    if role == "stik" and "stik" in permissions:
        definitions.append(
            {
                "task_type_id": "stik",
                "quantity_type": "stik",
                "capacity_per_day": configured_capacity,
                "unit": "stik",
            }
        )

    if role == "broend" and "broend" in permissions:
        definitions.append(
            {
                "task_type_id": "broend",
                "quantity_type": "broende",
                "capacity_per_day": configured_capacity,
                "unit": "brønd",
            }
        )

    if role == "dtvk":
        for task_type_id in (
            "stikforberedelse",
            "kontrol",
        ):
            if (
                task_type_id in permissions
                and configured_capacity > 0
            ):
                definitions.append(
                    {
                        "task_type_id": task_type_id,
                        "quantity_type": "stik",
                        "capacity_per_day": (
                            configured_capacity
                        ),
                        "unit": "stik",
                    }
                )

    # Den nuværende DTVK-varighed bruger disse
    # to produktionstal.
    if "dtvk" in permissions:
        definitions.extend(
            [
                {
                    "task_type_id": "dtvk",
                    "quantity_type": (
                        "hovedledning_meter"
                    ),
                    "capacity_per_day": 700.0,
                    "unit": "meter",
                },
                {
                    "task_type_id": "dtvk",
                    "quantity_type": "stik",
                    "capacity_per_day": 20.0,
                    "unit": "stik",
                },
            ]
        )

    return [
        definition
        for definition in definitions
        if definition["capacity_per_day"] > 0
    ]


def seed_teams(
    filename: Path = DEFAULT_TEAM_FILE,
) -> dict[str, int]:
    with filename.open("r", encoding="utf-8") as file:
        team_data = json.load(file)

    result = {
        "teams_created": 0,
        "teams_updated": 0,
        "permissions_created": 0,
        "permissions_updated": 0,
        "permissions_deactivated": 0,
        "capacities_created": 0,
        "capacities_updated": 0,
        "capacities_deactivated": 0,
    }

    with SessionLocal() as session:
        valid_task_types = set(
            session.scalars(
                select(TaskType.id)
            ).all()
        )

        for item in team_data:
            team_id = str(item["id"])
            calendar_id = str(item["calendar_id"])

            if session.get(
                WorkCalendar,
                calendar_id,
            ) is None:
                raise ValueError(
                    f"Kalenderen '{calendar_id}' findes "
                    f"ikke for holdet '{team_id}'. "
                    "Kør seed_calendars først."
                )

            team = session.get(Team, team_id)

            if team is None:
                team = Team(
                    id=team_id,
                    name=str(item["name"]),
                )
                session.add(team)
                result["teams_created"] += 1
            else:
                result["teams_updated"] += 1

            team.name = str(item["name"])
            team.role = str(item.get("role") or "")
            team.calendar_id = calendar_id
            team.active = bool(
                item.get("active", True)
            )
            team.notes = str(
                item.get("notes") or ""
            )

            session.flush()

            desired_permissions = (
                resolve_task_permissions(
                    item,
                    valid_task_types,
                )
            )

            existing_permissions = {
                permission.task_type_id: permission
                for permission in session.scalars(
                    select(TeamTaskPermission).where(
                        TeamTaskPermission.team_id
                        == team_id
                    )
                )
            }

            for task_type_id in desired_permissions:
                permission = existing_permissions.pop(
                    task_type_id,
                    None,
                )

                if permission is None:
                    permission = TeamTaskPermission(
                        team_id=team_id,
                        task_type_id=task_type_id,
                        active=True,
                    )
                    session.add(permission)
                    result[
                        "permissions_created"
                    ] += 1
                else:
                    permission.active = True
                    permission.valid_to = None
                    result[
                        "permissions_updated"
                    ] += 1

            for obsolete_permission in (
                existing_permissions.values()
            ):
                if obsolete_permission.active:
                    obsolete_permission.active = False
                    result[
                        "permissions_deactivated"
                    ] += 1

            desired_capacities = {
                (
                    definition["task_type_id"],
                    definition["quantity_type"],
                ): definition
                for definition in capacity_definitions(
                    item,
                    desired_permissions,
                )
            }

            existing_capacities = {
                (
                    capacity.task_type_id,
                    capacity.quantity_type,
                ): capacity
                for capacity in session.scalars(
                    select(TeamCapacityRate).where(
                        TeamCapacityRate.team_id
                        == team_id
                    )
                )
            }

            for key, definition in (
                desired_capacities.items()
            ):
                capacity = existing_capacities.pop(
                    key,
                    None,
                )

                if capacity is None:
                    capacity = TeamCapacityRate(
                        team_id=team_id,
                        task_type_id=definition[
                            "task_type_id"
                        ],
                        quantity_type=definition[
                            "quantity_type"
                        ],
                        capacity_per_day=definition[
                            "capacity_per_day"
                        ],
                        unit=definition["unit"],
                        active=True,
                    )
                    session.add(capacity)
                    result[
                        "capacities_created"
                    ] += 1
                else:
                    capacity.capacity_per_day = (
                        definition[
                            "capacity_per_day"
                        ]
                    )
                    capacity.unit = definition["unit"]
                    capacity.active = True
                    capacity.valid_to = None
                    result[
                        "capacities_updated"
                    ] += 1

            for obsolete_capacity in (
                existing_capacities.values()
            ):
                if obsolete_capacity.active:
                    obsolete_capacity.active = False
                    result[
                        "capacities_deactivated"
                    ] += 1

        session.commit()

    return result


if __name__ == "__main__":
    import_result = seed_teams()

    print("Hold importeret:")
    for key, value in import_result.items():
        print(f"- {key}: {value}")
