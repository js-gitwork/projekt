from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from projektstyring.backend.database.connection import (
    SessionLocal,
)
from projektstyring.backend.db_models import (
    Installation,
    InstallationProgress,
    Project,
    ProjectTask,
    Stretch,
    TaskAssignment,
    TaskQuantity,
    TaskType,
    Team,
)


TASK_SEQUENCES = {
    "forarbejde": 10,
    "hovedledning": 20,
    "stikforberedelse": 30,
    "stik": 40,
    "kontrol": 50,
    "korthat": 60,
    "broend": 70,
    "dtvk": 80,
    "broendscanning": 90,
}


def parse_optional_date(
    value: Any,
) -> date | None:
    if not value:
        return None

    if isinstance(value, date):
        return value

    return date.fromisoformat(
        str(value)
    )


def integer_value(
    value: Any,
) -> int:
    if value in (None, ""):
        return 0

    return int(value)


def float_value(
    value: Any,
) -> float:
    if value in (None, ""):
        return 0.0

    return float(value)


def installation_has_assignment(
    project: dict,
    task_type: str,
    installation_no: str,
) -> bool:
    assignments = project.get(
        "task_assignments",
        {},
    )

    task_assignments = assignments.get(
        task_type,
        [],
    )

    for assignment in task_assignments:
        installation_numbers = {
            str(value)
            for value in assignment.get(
                "installations",
                [],
            )
        }

        if (
            installation_no
            in installation_numbers
        ):
            return True

    return False


def get_or_create_project(
    session: Session,
    project_data: dict,
) -> tuple[Project, bool]:
    project_id = str(
        project_data["id"]
    )

    project = session.get(
        Project,
        project_id,
    )

    created = project is None

    if project is None:
        project = Project(
            id=project_id,
            name=str(
                project_data.get("name")
                or project_id
            ),
        )

        session.add(project)

    project.name = str(
        project_data.get("name")
        or project_id
    )

    project.customer = str(
        project_data.get("customer")
        or ""
    )

    project.city = str(
        project_data.get("city")
        or ""
    )

    project.start_date = (
        parse_optional_date(
            project_data.get(
                "start_date"
            )
        )
    )

    project.status = str(
        project_data.get("status")
        or "upcoming"
    )

    project.notes = str(
        project_data.get("notes")
        or ""
    )

    return project, created


def get_or_create_installation(
    session: Session,
    project_id: str,
    installation_data: dict,
    default_sequence: int,
) -> tuple[Installation, bool]:
    installation_no = str(
        installation_data["id"]
    )

    statement = (
        select(Installation)
        .where(
            Installation.project_id
            == project_id
        )
        .where(
            Installation.installation_no
            == installation_no
        )
    )

    installation = session.scalar(
        statement
    )

    created = installation is None

    if installation is None:
        installation = Installation(
            project_id=project_id,
            installation_no=(
                installation_no
            ),
            sequence=default_sequence,
        )

        session.add(
            installation
        )

    installation.sequence = (
        integer_value(
            installation_data.get(
                "sequence"
            )
            or default_sequence
        )
    )

    installation.active = bool(
        installation_data.get(
            "active",
            True,
        )
    )

    installation.hoveddato = (
        parse_optional_date(
            installation_data.get(
                "hoveddato"
            )
        )
    )

    installation.expected_stik = (
        integer_value(
            installation_data.get(
                "expected_stik"
            )
        )
    )

    installation.active_stik = (
        integer_value(
            installation_data.get(
                "active_stik"
            )
        )
    )

    installation.opened_stik = (
        integer_value(
            installation_data.get(
                "opened_stik"
            )
        )
    )

    installation.langhatte = (
        integer_value(
            installation_data.get(
                "langhatte"
            )
        )
    )

    installation.korthatte_extra = (
        integer_value(
            installation_data.get(
                "korthatte_extra"
            )
        )
    )

    installation.broende = (
        integer_value(
            installation_data.get(
                "broende"
            )
        )
    )

    installation.bronde_total = (
        integer_value(
            installation_data.get(
                "bronde_total"
            )
        )
    )

    installation.hovedledning_meter = (
        float_value(
            installation_data.get(
                "hovedledning_meter"
            )
            or installation_data.get(
                "main_length_m"
            )
        )
    )

    installation.notes = str(
        installation_data.get("notes")
        or ""
    )

    session.flush()

    return installation, created


def synchronize_progress(
    session: Session,
    installation: Installation,
    installation_data: dict,
) -> None:
    progress_data = (
        installation_data.get(
            "progress"
        )
    )

    if not isinstance(
        progress_data,
        dict,
    ):
        if (
            installation.progress
            is not None
        ):
            session.delete(
                installation.progress
            )

        return

    progress = (
        installation.progress
    )

    if progress is None:
        progress = InstallationProgress(
            installation_id=(
                installation.id
            ),
        )

        session.add(progress)

    progress.opmaaling = (
        float(
            progress_data[
                "opmaaling"
            ]
        )
        if progress_data.get(
            "opmaaling"
        )
        not in (None, "")
        else None
    )

    progress.forarbejde = (
        float(
            progress_data[
                "forarbejde"
            ]
        )
        if progress_data.get(
            "forarbejde"
        )
        not in (None, "")
        else None
    )

    progress.stikopmaaling = (
        float(
            progress_data[
                "stikopmaaling"
            ]
        )
        if progress_data.get(
            "stikopmaaling"
        )
        not in (None, "")
        else None
    )

    progress.hovedledning = (
        float(
            progress_data[
                "hovedledning"
            ]
        )
        if progress_data.get(
            "hovedledning"
        )
        not in (None, "")
        else None
    )

    progress.stikaabning = (
        float(
            progress_data[
                "stikaabning"
            ]
        )
        if progress_data.get(
            "stikaabning"
        )
        not in (None, "")
        else None
    )

    progress.source = str(
        progress_data.get(
            "source"
        )
        or "project_sync"
    )

    progress.raw_data = dict(
        progress_data
    )


def synchronize_stretches(
    session: Session,
    installation: Installation,
    installation_data: dict,
) -> None:
    stretch_data = (
        installation_data.get(
            "stretches"
        )
    )

    if not isinstance(
        stretch_data,
        list,
    ):
        stretch_data = []

    existing_stretches = {
        stretch.sequence: stretch
        for stretch in session.scalars(
            select(Stretch).where(
                Stretch.installation_id
                == installation.id
            )
        )
    }

    synchronized_sequences = set()

    for sequence, item in enumerate(
        stretch_data,
        start=1,
    ):
        synchronized_sequences.add(
            sequence
        )

        stretch = (
            existing_stretches.get(
                sequence
            )
        )

        if stretch is None:
            stretch = Stretch(
                installation_id=(
                    installation.id
                ),
                sequence=sequence,
            )

            session.add(stretch)

        stretch.from_brond = str(
            item.get("from_brond")
            or ""
        )

        stretch.to_brond = str(
            item.get("to_brond")
            or ""
        )

        stretch.length_m = (
            float_value(
                item.get("length_m")
            )
        )

        stretch.dimension = str(
            item.get("dimension")
            or ""
        )

        stretch.material = str(
            item.get("material")
            or ""
        )

        stretch.stik = integer_value(
            item.get("stik")
        )

        stretch.notes = str(
            item.get("notes")
            or ""
        )

        known_fields = {
            "from_brond",
            "to_brond",
            "length_m",
            "dimension",
            "material",
            "stik",
            "notes",
        }

        stretch.metadata_data = {
            key: value
            for key, value
            in item.items()
            if key not in known_fields
        }

    for (
        sequence,
        obsolete_stretch,
    ) in existing_stretches.items():
        if (
            sequence
            not in synchronized_sequences
        ):
            session.delete(
                obsolete_stretch
            )


def get_task_type(
    session: Session,
    task_type_id: str,
) -> TaskType:
    task_type = session.get(
        TaskType,
        task_type_id,
    )

    if task_type is None:
        raise ValueError(
            f"Opgavetypen "
            f"'{task_type_id}' "
            "findes ikke i databasen."
        )

    return task_type


def get_or_create_task(
    session: Session,
    project_id: str,
    installation_id: int,
    task_type_id: str,
    *,
    fixed_start_date: (
        date | None
    ) = None,
) -> tuple[ProjectTask, bool]:
    get_task_type(
        session,
        task_type_id,
    )

    statement = (
        select(ProjectTask)
        .where(
            ProjectTask.installation_id
            == installation_id
        )
        .where(
            ProjectTask.task_type_id
            == task_type_id
        )
    )

    task = session.scalar(
        statement
    )

    created = task is None

    if task is None:
        task = ProjectTask(
            project_id=project_id,
            installation_id=(
                installation_id
            ),
            task_type_id=task_type_id,
            sequence=(
                TASK_SEQUENCES[
                    task_type_id
                ]
            ),
        )

        session.add(task)

    task.project_id = project_id

    task.sequence = (
        TASK_SEQUENCES[
            task_type_id
        ]
    )

    task.active = True
    task.status = "pending"
    task.source = "project_sync"

    if fixed_start_date:
        task.scheduling_mode = "fixed"

        task.fixed_start_date = (
            fixed_start_date
        )

    else:
        task.scheduling_mode = (
            "calculated"
        )

        task.fixed_start_date = None

    session.flush()

    return task, created


def synchronize_quantities(
    session: Session,
    task: ProjectTask,
    quantities: dict[
        str,
        tuple[float, str],
    ],
) -> None:
    existing_quantities = {
        quantity.quantity_type: quantity
        for quantity in session.scalars(
            select(TaskQuantity).where(
                TaskQuantity.project_task_id
                == task.id
            )
        )
    }

    for (
        quantity_type,
        (value, unit),
    ) in quantities.items():
        quantity = (
            existing_quantities.pop(
                quantity_type,
                None,
            )
        )

        if quantity is None:
            quantity = TaskQuantity(
                project_task_id=task.id,
                quantity_type=(
                    quantity_type
                ),
                value=value,
                unit=unit,
            )

            session.add(quantity)

        else:
            quantity.value = value
            quantity.unit = unit

    # Mængder, som ikke længere findes i den
    # indkommende projekttilstand, fjernes fra
    # den aktuelle opgave.
    for obsolete_quantity in (
        existing_quantities.values()
    ):
        session.delete(
            obsolete_quantity
        )


def desired_tasks_for_installation(
    project: dict,
    installation_data: dict,
) -> dict[str, dict[str, Any]]:
    installation_no = str(
        installation_data["id"]
    )

    expected_stik = integer_value(
        installation_data.get(
            "expected_stik"
        )
    )

    active_stik = integer_value(
        installation_data.get(
            "active_stik"
        )
    )

    planned_stik = (
        active_stik
        or expected_stik
    )

    langhatte = integer_value(
        installation_data.get(
            "langhatte"
        )
    )

    korthatte_extra = integer_value(
        installation_data.get(
            "korthatte_extra"
        )
    )

    korthatte_total = (
        langhatte
        + korthatte_extra
    )

    broende = integer_value(
        installation_data.get(
            "broende"
        )
    )

    hovedledning_meter = (
        float_value(
            installation_data.get(
                "hovedledning_meter"
            )
            or installation_data.get(
                "main_length_m"
            )
        )
    )

    hoveddato = parse_optional_date(
        installation_data.get(
            "hoveddato"
        )
    )

    tasks: dict[
        str,
        dict[str, Any],
    ] = {}

    if (
        hoveddato
        or installation_has_assignment(
            project,
            "hovedledning",
            installation_no,
        )
    ):
        quantities = {}

        if hovedledning_meter > 0:
            quantities[
                "hovedledning_meter"
            ] = (
                hovedledning_meter,
                "meter",
            )

        tasks["hovedledning"] = {
            "fixed_start_date": (
                hoveddato
            ),
            "quantities": quantities,
        }

    if planned_stik > 0:
        stik_quantity = {
            "stik": (
                float(planned_stik),
                "stik",
            ),
        }

        for task_type in (
            "stikforberedelse",
            "stik",
            "kontrol",
        ):
            if installation_has_assignment(
                project,
                task_type,
                installation_no,
            ):
                tasks[task_type] = {
                    "fixed_start_date": (
                        None
                    ),
                    "quantities": (
                        stik_quantity
                    ),
                }

    if (
        korthatte_total > 0
        and installation_has_assignment(
            project,
            "korthat",
            installation_no,
        )
    ):
        tasks["korthat"] = {
            "fixed_start_date": None,
            "quantities": {
                "korthatte": (
                    float(
                        korthatte_total
                    ),
                    "stik",
                ),
            },
        }

    if (
        broende > 0
        and installation_has_assignment(
            project,
            "broend",
            installation_no,
        )
    ):
        tasks["broend"] = {
            "fixed_start_date": None,
            "quantities": {
                "broende": (
                    float(broende),
                    "brønd",
                ),
            },
        }

    if (
        (
            hovedledning_meter > 0
            or planned_stik > 0
        )
        and installation_has_assignment(
            project,
            "dtvk",
            installation_no,
        )
    ):
        dtvk_quantities = {}

        if hovedledning_meter > 0:
            dtvk_quantities[
                "hovedledning_meter"
            ] = (
                hovedledning_meter,
                "meter",
            )

        if planned_stik > 0:
            dtvk_quantities[
                "stik"
            ] = (
                float(planned_stik),
                "stik",
            )

        tasks["dtvk"] = {
            "fixed_start_date": None,
            "quantities": (
                dtvk_quantities
            ),
        }

    return tasks


def find_assigned_team_id(
    project: dict,
    task_type_id: str,
    installation_no: str,
) -> str | None:
    task_assignments = (
        project.get(
            "task_assignments",
            {},
        ).get(
            task_type_id,
            [],
        )
    )

    for assignment in task_assignments:
        installation_numbers = {
            str(value)
            for value in assignment.get(
                "installations",
                [],
            )
        }

        if (
            installation_no
            in installation_numbers
        ):
            team_id = str(
                assignment.get("team")
                or ""
            ).strip()

            return (
                team_id
                or None
            )

    return None


def synchronize_task_assignment(
    session: Session,
    task: ProjectTask,
    team_id: str | None,
) -> tuple[int, int, int]:
    existing_assignments = list(
        session.scalars(
            select(
                TaskAssignment
            ).where(
                TaskAssignment.project_task_id
                == task.id
            )
        )
    )

    created_count = 0
    updated_count = 0
    deactivated_count = 0

    if team_id is None:
        for assignment in (
            existing_assignments
        ):
            if assignment.active:
                assignment.active = False

                assignment.valid_to = (
                    date.today()
                )

                deactivated_count += 1

        return (
            created_count,
            updated_count,
            deactivated_count,
        )

    team = session.get(
        Team,
        team_id,
    )

    if team is None:
        raise ValueError(
            f"Holdet '{team_id}' "
            "findes ikke i databasen."
        )

    matching_assignment = None

    for assignment in (
        existing_assignments
    ):
        if (
            assignment.team_id
            == team_id
            and assignment.valid_from
            is None
        ):
            matching_assignment = (
                assignment
            )
            break

    if matching_assignment is None:
        matching_assignment = (
            TaskAssignment(
                project_task_id=(
                    task.id
                ),
                team_id=team_id,
                active=True,
                valid_from=None,
                valid_to=None,
                assigned_by=None,
                source="project_sync",
                reason=(
                    "Synkroniseret fra "
                    "projektets "
                    "task_assignments."
                ),
            )
        )

        session.add(
            matching_assignment
        )

        created_count += 1

    else:
        matching_assignment.active = (
            True
        )

        matching_assignment.valid_to = (
            None
        )

        matching_assignment.source = (
            "project_sync"
        )

        matching_assignment.reason = (
            "Synkroniseret fra projektets "
            "task_assignments."
        )

        updated_count += 1

    for assignment in (
        existing_assignments
    ):
        if (
            assignment
            is matching_assignment
        ):
            continue

        if assignment.active:
            assignment.active = False

            assignment.valid_to = (
                date.today()
            )

            deactivated_count += 1

    return (
        created_count,
        updated_count,
        deactivated_count,
    )


def synchronize_tasks(
    session: Session,
    project: dict,
    installation: Installation,
    installation_data: dict,
) -> tuple[int, int, int, int, int]:
    desired_tasks = (
        desired_tasks_for_installation(
            project,
            installation_data,
        )
    )

    existing_tasks = {
        task.task_type_id: task
        for task in session.scalars(
            select(ProjectTask).where(
                ProjectTask.installation_id
                == installation.id
            )
        )
    }

    tasks_created = 0
    tasks_updated = 0

    assignments_created = 0
    assignments_updated = 0
    assignments_deactivated = 0

    for (
        task_type_id,
        task_data,
    ) in desired_tasks.items():
        task, created = (
            get_or_create_task(
                session=session,
                project_id=(
                    installation.project_id
                ),
                installation_id=(
                    installation.id
                ),
                task_type_id=(
                    task_type_id
                ),
                fixed_start_date=(
                    task_data[
                        "fixed_start_date"
                    ]
                ),
            )
        )

        synchronize_quantities(
            session=session,
            task=task,
            quantities=(
                task_data[
                    "quantities"
                ]
            ),
        )

        team_id = (
            find_assigned_team_id(
                project=project,
                task_type_id=(
                    task_type_id
                ),
                installation_no=(
                    installation.installation_no
                ),
            )
        )

        (
            assignment_created,
            assignment_updated,
            assignment_deactivated,
        ) = synchronize_task_assignment(
            session=session,
            task=task,
            team_id=team_id,
        )

        assignments_created += (
            assignment_created
        )

        assignments_updated += (
            assignment_updated
        )

        assignments_deactivated += (
            assignment_deactivated
        )

        existing_tasks.pop(
            task_type_id,
            None,
        )

        if created:
            tasks_created += 1
        else:
            tasks_updated += 1

    for obsolete_task in (
        existing_tasks.values()
    ):
        obsolete_task.active = False

        (
            _,
            _,
            assignment_deactivated,
        ) = synchronize_task_assignment(
            session=session,
            task=obsolete_task,
            team_id=None,
        )

        assignments_deactivated += (
            assignment_deactivated
        )

    return (
        tasks_created,
        tasks_updated,
        assignments_created,
        assignments_updated,
        assignments_deactivated,
    )


def synchronize_project(
    project_data: dict,
    *,
    session: Session | None = None,
) -> dict[str, int | str]:
    """
    Synkroniserer en komplet projekttilstand med databasen.

    Funktionen kan eje sin egen transaktion eller indgå i en
    eksisterende transaktion ved at modtage en Session.

    Eksisterende historik slettes ikke unødigt. Installationer og
    opgaver, som ikke længere findes i den indkommende tilstand,
    deaktiveres hvor det er relevant.
    """

    owns_session = session is None

    database_session = (
        session
        or SessionLocal()
    )

    result: dict[
        str,
        int | str,
    ] = {
        "project_id": str(
            project_data["id"]
        ),
        "projects_created": 0,
        "projects_updated": 0,
        "installations_created": 0,
        "installations_updated": 0,
        "tasks_created": 0,
        "tasks_updated": 0,
        "assignments_created": 0,
        "assignments_updated": 0,
        "assignments_deactivated": 0,
    }

    try:
        (
            _,
            project_created,
        ) = get_or_create_project(
            database_session,
            project_data,
        )

        if project_created:
            result[
                "projects_created"
            ] = 1
        else:
            result[
                "projects_updated"
            ] = 1

        database_session.flush()

        synchronized_installation_numbers = (
            set()
        )

        for (
            default_sequence,
            installation_data,
        ) in enumerate(
            project_data.get(
                "installations",
                [],
            ),
            start=1,
        ):
            installation_no = str(
                installation_data[
                    "id"
                ]
            )

            synchronized_installation_numbers.add(
                installation_no
            )

            (
                installation,
                installation_created,
            ) = get_or_create_installation(
                session=(
                    database_session
                ),
                project_id=str(
                    project_data["id"]
                ),
                installation_data=(
                    installation_data
                ),
                default_sequence=(
                    default_sequence
                ),
            )

            if installation_created:
                result[
                    "installations_created"
                ] += 1
            else:
                result[
                    "installations_updated"
                ] += 1

            synchronize_progress(
                session=(
                    database_session
                ),
                installation=installation,
                installation_data=(
                    installation_data
                ),
            )

            synchronize_stretches(
                session=(
                    database_session
                ),
                installation=installation,
                installation_data=(
                    installation_data
                ),
            )

            (
                tasks_created,
                tasks_updated,
                assignments_created,
                assignments_updated,
                assignments_deactivated,
            ) = synchronize_tasks(
                session=(
                    database_session
                ),
                project=project_data,
                installation=installation,
                installation_data=(
                    installation_data
                ),
            )

            result[
                "tasks_created"
            ] += tasks_created

            result[
                "tasks_updated"
            ] += tasks_updated

            result[
                "assignments_created"
            ] += assignments_created

            result[
                "assignments_updated"
            ] += assignments_updated

            result[
                "assignments_deactivated"
            ] += (
                assignments_deactivated
            )

        existing_installations = (
            database_session.scalars(
                select(
                    Installation
                ).where(
                    Installation.project_id
                    == str(
                        project_data["id"]
                    )
                )
            )
        )

        # Installationer, som ikke længere findes i den
        # indkommende projekttilstand, deaktiveres i
        # stedet for at blive slettet.
        for installation in (
            existing_installations
        ):
            if (
                installation.installation_no
                not in
                synchronized_installation_numbers
            ):
                installation.active = (
                    False
                )

                for task in (
                    installation.tasks
                ):
                    task.active = False

        if owns_session:
            database_session.commit()
        else:
            database_session.flush()

        return result

    except Exception:
        if owns_session:
            database_session.rollback()

        raise

    finally:
        if owns_session:
            database_session.close()
