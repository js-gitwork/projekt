VALID_SURVEY_STATUSES = {
    "pending",
    "in_progress",
    "completed",
}


def get_survey(project):
    return project.get("survey", {})


def update_status(project, status):
    if status not in VALID_SURVEY_STATUSES:
        raise ValueError(f"Ugyldig survey-status: {status}")

    project["survey"]["status"] = status
    return project


def assign_responsible(project, person):
    project["survey"]["responsible"] = person
    return project


def set_planned_date(project, planned_date):
    project["survey"]["planned_date"] = planned_date
    return project


def set_completed_date(project, completed_date):
    project["survey"]["completed_date"] = completed_date
    return project


def update_notes(project, notes):
    project["survey"]["notes"] = notes
    return project


def update_measurements(
    project,
    *,
    expected_stik=None,
    expected_broende=None,
    main_dimensions=None,
    notes=None,
):
    measurements = project["survey"]["measurements"]

    if expected_stik is not None:
        measurements["expected_stik"] = expected_stik

    if expected_broende is not None:
        measurements["expected_broende"] = expected_broende

    if main_dimensions is not None:
        measurements["main_dimensions"] = list(main_dimensions)

    if notes is not None:
        measurements["notes"] = notes

    return project