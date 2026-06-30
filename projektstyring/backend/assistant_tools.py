from projektstyring.backend.decision_engine import simulate_project_start_change
from projektstyring.backend.project_repository import ProjectRepository


repo = ProjectRepository()


def value_of(item, key, default=""):
    if isinstance(item, dict):
        return item.get(key, default)

    return getattr(item, key, default)


def get_all_projects():
    projects = repo.list_projects()

    return [
        {
            "id": value_of(project, "id"),
            "name": value_of(project, "name"),
            "customer": value_of(project, "customer"),
            "city": value_of(project, "city"),
            "status": value_of(project, "status"),
            "start_date": str(value_of(project, "start_date")),
        }
        for project in projects
    ]


def get_project(project_id: str):
    return repo.load_project(project_id)


def run_simulate_project_start_change(
    project_id: str,
    new_start_date: str,
):
    return simulate_project_start_change(
        project_id,
        new_start_date,
    )


TOOLS = {
    "get_all_projects": get_all_projects,
    "get_project": get_project,
    "simulate_project_start_change": run_simulate_project_start_change,
}


def run_tool(tool_name: str, args: dict | None = None):
    args = args or {}

    if tool_name not in TOOLS:
        return {
            "error": f"Ukendt tool: {tool_name}",
            "available_tools": list(TOOLS.keys()),
        }

    return TOOLS[tool_name](**args)


def available_tools():
    return list(TOOLS.keys())