from copy import deepcopy
from datetime import datetime


def create_snapshot(project, reason="manual"):
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_id": project.get("id"),
        "reason": reason,
        "status": project.get("status"),
        "installations": deepcopy(project.get("installations", [])),
        "task_assignments": deepcopy(project.get("task_assignments", {})),
    }


def add_snapshot(project, reason="manual"):
    project.setdefault("snapshots", [])

    snapshot = create_snapshot(project, reason)
    project["snapshots"].append(snapshot)

    return project


def get_latest_snapshot(project):
    snapshots = project.get("snapshots", [])

    if not snapshots:
        return None

    return snapshots[-1]
