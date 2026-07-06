import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from projektstyring.backend.project_repository import ProjectRepository


def main():
    repo = ProjectRepository()

    project = repo.load_project("V165460")

    print("Projekt:", project["id"])
    print("Status:", project.get("status"))
    print("Survey:", project.get("survey"))

    assert "survey" in project
    assert isinstance(project["survey"], dict)
    assert "status" in project["survey"]
    assert "measurements" in project["survey"]

    print("OK: Survey-model findes og er gyldig.")


if __name__ == "__main__":
    main()
