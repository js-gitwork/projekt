from copy import deepcopy
from datetime import datetime


def create_baseline(project, plan=None):
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_id": project.get("id"),
        "status_at_creation": project.get("status"),
        "plan": deepcopy(plan or []),
        "installations": deepcopy(project.get("installations", [])),
        "task_assignments": deepcopy(project.get("task_assignments", {})),
    }


def has_baseline(project):
    return bool(project.get("baseline"))
