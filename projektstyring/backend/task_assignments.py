TASK_TYPES = [
    "hovedledning",
    "stikforberedelse",
    "stik",
    "kontrol",
    "korthat",
    "broend",
    "dtvk",
]

def empty_task_assignments():
    return {
        task_type: []
        for task_type in TASK_TYPES
    }


def ensure_task_assignments(project):
    if "task_assignments" not in project:
        project["task_assignments"] = empty_task_assignments()

    for task_type in TASK_TYPES:
        project["task_assignments"].setdefault(task_type, [])

    return project
