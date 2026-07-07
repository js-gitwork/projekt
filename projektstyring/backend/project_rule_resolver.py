from copy import deepcopy


def get_workflow_exceptions(project: dict) -> list[dict]:
    return project.get("workflow_exceptions", [])


def has_exception(
    project: dict,
    *,
    exception_type: str,
    task_type: str,
    installation_id: str,
    before_task_type: str | None = None,
) -> bool:
    installation_id = str(installation_id)

    for exception in get_workflow_exceptions(project):
        if exception.get("type") != exception_type:
            continue

        if exception.get("task_type") != task_type:
            continue

        if before_task_type:
            if exception.get("before_task_type") != before_task_type:
                continue

        installation_ids = [
            str(item)
            for item in exception.get("installation_ids", [])
        ]

        if installation_id in installation_ids:
            return True

    return False


def resolve_workflow_exceptions(project: dict) -> dict:
    """
    Returnerer en kopi af projektet, hvor godkendte workflow-undtagelser
    er gjort tilgængelige for planlæggeren.

    Denne funktion ændrer ikke originalprojektet.
    """

    resolved_project = deepcopy(project)

    approved_exceptions = [
        exception
        for exception in resolved_project.get("workflow_exceptions", [])
        if exception.get("approved") is True
    ]

    resolved_project["_resolved_workflow_exceptions"] = approved_exceptions

    return resolved_project


def get_resolved_exceptions(project: dict) -> list[dict]:
    return project.get("_resolved_workflow_exceptions", [])


def is_task_allowed_before(
    project: dict,
    *,
    task_type: str,
    before_task_type: str,
    installation_id: str,
) -> bool:
    installation_id = str(installation_id)

    for exception in get_resolved_exceptions(project):
        if exception.get("type") != "allow_task_before_dependency":
            continue

        if exception.get("task_type") != task_type:
            continue

        if exception.get("before_task_type") != before_task_type:
            continue

        installation_ids = [
            str(item)
            for item in exception.get("installation_ids", [])
        ]

        if installation_id in installation_ids:
            return True

    return False
