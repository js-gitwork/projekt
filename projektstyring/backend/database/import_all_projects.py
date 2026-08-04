from __future__ import annotations

import json
from pathlib import Path

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.database.import_project import import_project


DEFAULT_PROJECT_DIRECTORY = Path(
    "projektstyring/data/projects"
)


def import_all_projects(
    project_directory: Path = DEFAULT_PROJECT_DIRECTORY,
) -> dict:
    project_files = sorted(
        project_directory.glob("*_project.json")
    )

    summary = {
        "files_found": len(project_files),
        "projects_imported": 0,
        "projects_created": 0,
        "projects_updated": 0,
        "installations_created": 0,
        "installations_updated": 0,
        "tasks_created": 0,
        "tasks_updated": 0,
        "failed": [],
        "projects": [],
    }

    with SessionLocal() as session:
        try:
            for project_file in project_files:
                try:
                    with project_file.open(
                        "r",
                        encoding="utf-8",
                    ) as file:
                        project_data = json.load(file)

                    result = import_project(
                        project_data,
                        session=session,
                    )

                    summary["projects_imported"] += 1
                    summary["projects_created"] += int(
                        result["projects_created"]
                    )
                    summary["projects_updated"] += int(
                        result["projects_updated"]
                    )
                    summary["installations_created"] += int(
                        result["installations_created"]
                    )
                    summary["installations_updated"] += int(
                        result["installations_updated"]
                    )
                    summary["tasks_created"] += int(
                        result["tasks_created"]
                    )
                    summary["tasks_updated"] += int(
                        result["tasks_updated"]
                    )

                    summary["projects"].append(
                        {
                            "file": project_file.name,
                            **result,
                        }
                    )

                except Exception as error:
                    summary["failed"].append(
                        {
                            "file": project_file.name,
                            "error": str(error),
                        }
                    )

            if summary["failed"]:
                session.rollback()
            else:
                session.commit()

        except Exception:
            session.rollback()
            raise

    return summary


def print_summary(summary: dict) -> None:
    print("\nProjektimport")
    print("-" * 60)
    print(f"Filer fundet:             {summary['files_found']}")
    print(
        f"Projekter importeret:     "
        f"{summary['projects_imported']}"
    )
    print(
        f"Projekter oprettet:       "
        f"{summary['projects_created']}"
    )
    print(
        f"Projekter opdateret:      "
        f"{summary['projects_updated']}"
    )
    print(
        f"Installationer oprettet:  "
        f"{summary['installations_created']}"
    )
    print(
        f"Installationer opdateret: "
        f"{summary['installations_updated']}"
    )
    print(
        f"Opgaver oprettet:         "
        f"{summary['tasks_created']}"
    )
    print(
        f"Opgaver opdateret:        "
        f"{summary['tasks_updated']}"
    )

    if summary["failed"]:
        print("\nFejl")
        print("-" * 60)

        for failure in summary["failed"]:
            print(
                f"{failure['file']}: "
                f"{failure['error']}"
            )

        print(
            "\nIngen ændringer blev gemt, fordi mindst "
            "én projektimport fejlede."
        )
    else:
        print("\nAlle projekter blev importeret succesfuldt.")


if __name__ == "__main__":
    import_summary = import_all_projects()
    print_summary(import_summary)

    if import_summary["failed"]:
        raise SystemExit(1)
