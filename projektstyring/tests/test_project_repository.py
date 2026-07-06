from projektstyring.backend.project_repository import (
    ProjectRepository,
)

repo = ProjectRepository()

print("\nPROJEKTER")
print("-" * 60)

for project in repo.list_projects():
    print(
        project["id"],
        project["name"],
        project["start_date"],
    )

print("\nLOAD V165460")
print("-" * 60)

project = repo.load_project("V165460")

print(project["id"])
print(project["name"])
print(
    "Installationer:",
    len(project["installations"])
)
