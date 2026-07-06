from projektstyring.backend.task_assignments import empty_task_assignments
from projektstyring.backend.survey_model import default_survey


def create_project(
    *,
    project_id,
    name,
    customer="",
    city="",
    start_date="",
    notes="Oprettet som udkast.",
):
    return {
        "id": project_id.strip(),
        "name": name.strip(),
        "customer": customer.strip(),
        "city": city.strip(),
        "start_date": start_date,
        "status": "survey",
        "survey": default_survey(start_date),
        "task_assignments": empty_task_assignments(),
        "installations": [],
        "notes": notes,
    }
