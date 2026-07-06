REFERENCE_WORDS = {
    "de",
    "dem",
    "disse",
    "de to",
    "begge",
    "dem begge",
}


def refers_to_previous_projects(text):
    lower = text.strip().lower()

    return any(
        word in lower
        for word in REFERENCE_WORDS
    )


def resolve_project_reference(text, context):
    if not refers_to_previous_projects(text):
        return None

    if context.get("topic") != "projects":
        return None

    project_ids = context.get("project_ids", [])

    if not project_ids:
        return None

    return {
        "type": "project_reference",
        "project_ids": project_ids,
        "source": "last_context",
    }
