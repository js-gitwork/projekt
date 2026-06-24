from projektstyring.backend.project_repository import ProjectRepository


repo = ProjectRepository()


def get_all_projects():
    """
    Returnerer rå projektdata til AI/tools.
    """

    projects = repo.list_projects()

    result = []

    for p in projects:
        result.append(
            {
                "id": getattr(p, "id", ""),
                "name": getattr(p, "name", ""),
                "customer": getattr(p, "customer", ""),
                "city": getattr(p, "city", ""),
                "status": getattr(p, "status", None),
                "start_date": str(getattr(p, "start_date", "")),
            }
        )

    return result


def format_project_list():
    """
    Returnerer en pæn tekstliste til brugeren.
    """

    projects = get_all_projects()

    if not projects:
        return "Jeg kunne ikke finde nogen projekter."

    lines = []

    for project in projects:
        lines.append(
            f"• {project['id']} — {project['name']}"
        )

    return (
        f"Vi har {len(projects)} projekter:\n\n"
        + "\n".join(lines)
    )


def get_project(project_id: str):
    project = repo.load_project(project_id)

    return {
        "id": getattr(project, "id", ""),
        "name": getattr(project, "name", ""),
        "customer": getattr(project, "customer", ""),
        "city": getattr(project, "city", ""),
        "status": getattr(project, "status", None),
        "start_date": str(getattr(project, "start_date", "")),
        "installations": [
            {
                "id": getattr(i, "id", ""),
                "active": getattr(i, "active", True),
                "hoveddato": str(getattr(i, "hoveddato", "")),
                "expected_stik": getattr(i, "expected_stik", None),
                "active_stik": getattr(i, "active_stik", None),
                "langhatte": getattr(i, "langhatte", None),
                "korthatte_extra": getattr(i, "korthatte_extra", None),
                "broende": getattr(i, "broende", None),
            }
            for i in getattr(project, "installations", [])
        ],
        "assignments": getattr(project, "assignments", []),
    }


TOOLS = {
    "get_all_projects": get_all_projects,
    "get_project": get_project,
}


def run_tool(tool_name: str, args: dict | None = None):
    args = args or {}

    if tool_name not in TOOLS:
        return {
            "error": f"Ukendt tool: {tool_name}",
            "available_tools": list(TOOLS.keys()),
        }

    return TOOLS[tool_name](**args)