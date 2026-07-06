import pytest

from projektstyring.backend.survey_model import default_survey
from projektstyring.backend.survey_service import (
    assign_responsible,
    set_completed_date,
    set_planned_date,
    update_measurements,
    update_notes,
    update_status,
)


def make_project():
    return {
        "id": "VTEST",
        "survey": default_survey("2026-07-06"),
    }


def test_update_status():
    project = make_project()

    update_status(project, "in_progress")

    assert project["survey"]["status"] == "in_progress"


def test_update_status_rejects_invalid_status():
    project = make_project()

    with pytest.raises(ValueError):
        update_status(project, "wrong")


def test_assign_responsible():
    project = make_project()

    assign_responsible(project, "Jacob")

    assert project["survey"]["responsible"] == "Jacob"


def test_set_planned_date():
    project = make_project()

    set_planned_date(project, "2026-07-10")

    assert project["survey"]["planned_date"] == "2026-07-10"


def test_set_completed_date():
    project = make_project()

    set_completed_date(project, "2026-07-11")

    assert project["survey"]["completed_date"] == "2026-07-11"


def test_update_notes():
    project = make_project()

    update_notes(project, "Survey afventer opmåling.")

    assert project["survey"]["notes"] == "Survey afventer opmåling."


def test_update_measurements():
    project = make_project()

    update_measurements(
        project,
        expected_stik=14,
        expected_broende=3,
        main_dimensions=["Ø200", "Ø250"],
        notes="Målt på tegning.",
    )

    measurements = project["survey"]["measurements"]

    assert measurements["expected_stik"] == 14
    assert measurements["expected_broende"] == 3
    assert measurements["main_dimensions"] == ["Ø200", "Ø250"]
    assert measurements["notes"] == "Målt på tegning."