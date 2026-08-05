import pytest

from projektstyring.backend.project_workflow import (complete_survey, start_project,)
from projektstyring.backend.survey_model import default_survey


def make_project():
    return {
        "id": "VTEST",
        "status": "survey",
        "survey": default_survey(),
        "installations": [],
    }


def test_complete_survey():
    project = make_project()

    complete_survey(project, 3)

    assert project["status"] == "upcoming"
    assert project["survey"]["status"] == "completed"
    assert len(project["installations"]) == 3


def test_requires_survey_phase():
    project = make_project()
    project["status"] = "active"

    with pytest.raises(ValueError):
        complete_survey(project, 3)


def test_requires_installations():
    project = make_project()

    with pytest.raises(ValueError):
        complete_survey(project, 0)

def test_start_project_sets_active_status():
    project = make_project()
    complete_survey(project, 3)

    result = start_project(project)

    assert result["status"] == "active"
    assert result["deviations"] == []
    assert project["deviations"] == []