from projektstyring.backend.installation_service import create_installations
from projektstyring.backend.survey_service import update_status

def complete_survey(project, installation_count):
    """
    Afslutter survey-fasen og gør projektet klar til planlægning.
    """

    survey = project.get("survey")
    if survey is None:
        raise ValueError("Projektet har ikke et survey.")

    if project.get("status") != "survey":
        raise ValueError("Kun projekter i survey-fasen kan afslutte survey.")

    if installation_count <= 0:
        raise ValueError("Projektet skal opdeles i mindst én installation.")

    update_status(project, "completed")

    create_installations(project, installation_count)

    project["status"] = "upcoming"

    return project

def start_project(project):
    """
    Starter projektets udførelsesfase.

    Funktionen ændrer kun projektets domænetilstand.
    Permanent baselinehistorik oprettes af det kaldende databaselag.
    """

    if project.get("status") != "upcoming":
        raise ValueError(
            "Kun kommende projekter kan startes."
        )

    project["status"] = "active"
    project.setdefault("deviations", [])

    return project