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

def test_start_project_creates_baseline():
    project = make_project()
    complete_survey(project, 3)

    start_project(project)

    assert project["status"] == "active"
    assert project["baseline"]["project_id"] == "VTEST"
    assert len(project["baseline"]["installations"]) == 3
    assert project["deviations"] == []