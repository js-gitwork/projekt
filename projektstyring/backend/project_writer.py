import json
from pathlib import Path


def save_project(project: dict, directory="projektstyring/data/projects"):
    Path(directory).mkdir(parents=True, exist_ok=True)

    filename = (
        f"{directory}/"
        f"{project['id']}_project.json"
    )

    with open(
        filename,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            project,
            file,
            indent=4,
            ensure_ascii=False,
        )

    return filename
