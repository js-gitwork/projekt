from projektstyring.backend.installation_service import create_installations
from projektstyring.backend.survey_service import update_status
from projektstyring.backend.baseline_service import create_baseline, has_baseline

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

    Når projektet bliver active, gemmes et øjebliksbillede som baseline.
    Senere ændringer må gerne foretages, men kan sammenlignes med baseline.
    """

    if project.get("status") != "upcoming":
        raise ValueError("Kun kommende projekter kan startes.")

    if not has_baseline(project):
        project["baseline"] = create_baseline(project)

    project["status"] = "active"
    project.setdefault("deviations", [])

    return project