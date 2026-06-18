import json
from pathlib import Path


class ProjectRepository:

    def __init__(
        self,
        project_directory="projektstyring/data/projects",
    ):
        self.project_directory = Path(project_directory)

    def list_projects(self):
        projects = []

        for filename in sorted(
            self.project_directory.glob("*_project.json")
        ):
            try:
                with open(
                    filename,
                    "r",
                    encoding="utf-8",
                ) as file:
                    project = json.load(file)

                projects.append(
                    {
                        "id": project.get("id"),
                        "name": project.get("name"),
                        "customer": project.get("customer", ""),
                        "city": project.get("city", ""),
                        "start_date": project.get("start_date"),
                        "status": project.get("status", "upcoming"),
                        "file": filename.name,
                    }
                )

            except Exception as error:
                print(
                    f"Fejl ved læsning af {filename}: "
                    f"{error}"
                )

        return projects

    def load_project(
        self,
        project_id,
    ):
        filename = (
            self.project_directory
            / f"{project_id}_project.json"
        )

        with open(
            filename,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    def delete_project(
        self,
        project_id,
    ):
        filename = (
            self.project_directory
            / f"{project_id}_project.json"
        )

        if filename.exists():
            filename.unlink()
            return True

    def load_all_projects(self):
        projects = []

        for project_info in self.list_projects():
            try:
                projects.append(
                    self.load_project(project_info["id"])
                )
            except Exception as error:
                print(
                    f"Fejl ved læsning af projekt "
                    f"{project_info['id']}: {error}"
                )

        return projects

        return False
