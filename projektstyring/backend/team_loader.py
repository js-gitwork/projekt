import json

from projektstyring.backend.team_model import Team


def load_teams(filename: str) -> dict[str, Team]:
    with open(filename, "r", encoding="utf-8") as file:
        data = json.load(file)

    teams = {}

    for item in data:
        team = Team(
            id=item["id"],
            name=item["name"],
            role=item["role"],
            calendar_id=item["calendar_id"],
            capacity_per_day=item.get("capacity_per_day", 0),
            task_types=item.get("task_types", []),
            active=item.get("active", True),
        )

        teams[team.id] = team

    return teams
