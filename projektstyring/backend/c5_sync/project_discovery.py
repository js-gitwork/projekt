
"""Synkroniser C5's projektregister til Rørbots PostgreSQL-database.

C5 er autoritativ for projektregistrering og afslutningsstatus.
Eksisterende lokale planer og øvrige projektdata ændres ikke.

Kørsel:
    python -m projektstyring.backend.c5_sync.project_discovery
    python -m projektstyring.backend.c5_sync.project_discovery --dry-run
"""

import argparse
import re
from collections import Counter

from sqlalchemy import select

from projektstyring.backend.c5_sync.reader import C5_DATASET, connect
from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.project import Project, utc_now


PROJECT_NUMBER_PATTERN = re.compile(r"V([0-9]{6})", re.IGNORECASE)
MIN_PROJECT_NUMBER = 150000

C5_OPEN = 1
C5_CLOSED = 4


def eligible_project_id(value: object) -> str | None:
    """Returner et gyldigt produktionsprojektnummer eller None."""
    project_id = str(value or "").strip().upper()
    match = PROJECT_NUMBER_PATTERN.fullmatch(project_id)

    if match is None:
        return None

    if int(match.group(1)) <= MIN_PROJECT_NUMBER:
        return None

    return project_id


def fetch_c5_projects() -> dict[str, dict]:
    """Læs C5-projektregisteret uden at ændre C5."""
    connection = connect()

    try:
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                SELECT
                    LTRIM(RTRIM(NUMBER_)) AS project_id,
                    NAME,
                    ETPROSTATUS
                FROM dbo.PROJTABLE
                WHERE DATASET = %s
                """,
                (C5_DATASET,),
            )

            rows = cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()

    if not rows:
        raise RuntimeError(
            "C5 returnerede ingen projekter. Synkronisering afbrudt."
        )

    projects = {}

    for row in rows:
        project_id = eligible_project_id(row["project_id"])

        if project_id is None:
            continue

        if project_id in projects:
            raise RuntimeError(
                f"Dubleret C5-projektnummer: {project_id}"
            )

        status = row["ETPROSTATUS"]
        customer = str(row["NAME"] or "").strip()

        if len(customer) > 200:
            raise RuntimeError(
                f"Kundenavn overstiger 200 tegn: {project_id}"
            )

        projects[project_id] = {
            "customer": customer,
            "c5_status": status,
        }

    if not projects:
        raise RuntimeError(
            "Ingen gyldige C5-projekter fundet. Synkronisering afbrudt."
        )

    return projects


def sync_projects(dry_run: bool = False) -> Counter:
    """Opret nye projekter og luk eksisterende projekter efter C5-status."""
    c5_projects = fetch_c5_projects()
    counts = Counter()
    changes = []

    with SessionLocal() as session:
        with session.begin():
            existing_projects = {
                str(project.id).strip().upper(): project
                for project in session.scalars(select(Project)).all()
            }

            for project_id, c5_data in sorted(c5_projects.items()):
                c5_status = c5_data["c5_status"]
                project = existing_projects.get(project_id)

                if project is None:
                    if c5_status == C5_OPEN:
                        counts["CREATE"] += 1
                        changes.append(
                            ("CREATE", project_id, c5_data["customer"])
                        )

                        if not dry_run:
                            session.add(
                                Project(
                                    id=project_id,
                                    name=project_id,
                                    customer=c5_data["customer"],
                                    status="survey",
                                    is_closed=False,
                                )
                            )

                    elif c5_status == C5_CLOSED:
                        counts["SKIP_CLOSED"] += 1

                    else:
                        counts["SKIP_UNKNOWN"] += 1

                    continue

                if project.is_closed:
                    counts["KEEP_CLOSED"] += 1
                    continue

                if c5_status == C5_CLOSED:
                    counts["CLOSE"] += 1
                    changes.append(
                        ("CLOSE", project_id, project.name)
                    )

                    if not dry_run:
                        project.is_closed = True
                        project.updated_at = utc_now()

                else:
                    counts["KEEP"] += 1

    print()
    print("=== C5 PROJEKTOPDAGELSE ===")
    print("Tilstand:", "DRY RUN" if dry_run else "SYNKRONISERING")

    for action in (
        "CREATE",
        "CLOSE",
        "KEEP",
        "KEEP_CLOSED",
        "SKIP_CLOSED",
        "SKIP_UNKNOWN",
    ):
        print(f"{action}: {counts[action]}")

    if changes:
        print()
        print("Ændringer:")

        for action, project_id, name in changes:
            print(f"{action} | {project_id} | {name}")

    print()
    print(
        "Ingen data ændret."
        if dry_run
        else "PostgreSQL-synkronisering gennemført."
    )

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synkroniser projekter fra C5 til Rørbot."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Vis ændringer uden at skrive til PostgreSQL.",
    )

    arguments = parser.parse_args()
    sync_projects(dry_run=arguments.dry_run)


if __name__ == "__main__":
    main()
