def default_survey(start_date=None):
    return {
        "status": "pending",
        "planned_date": start_date,
        "completed_date": None,
        "responsible": None,
        "notes": "",
        "measurements": {
            "expected_stik": None,
            "expected_broende": None,
            "main_dimensions": [],
            "notes": "",
        },
    }


def ensure_survey(project):
    if "survey" not in project or not isinstance(project["survey"], dict):
        project["survey"] = default_survey(project.get("start_date"))

    project.setdefault("status", "survey")

    return project
