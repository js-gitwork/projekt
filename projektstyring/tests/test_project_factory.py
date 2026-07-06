from projektstyring.backend.project_factory import create_project


def test_create_project_defaults_to_survey_phase():
    project = create_project(
        project_id=" VTEST ",
        name=" Testprojekt ",
        customer=" Kunde ",
        city=" By ",
        start_date="2026-07-06",
    )

    assert project["id"] == "VTEST"
    assert project["name"] == "Testprojekt"
    assert project["customer"] == "Kunde"
    assert project["city"] == "By"
    assert project["start_date"] == "2026-07-06"
    assert project["status"] == "survey"
    assert project["survey"]["status"] == "pending"
    assert project["survey"]["planned_date"] == "2026-07-06"
    assert project["installations"] == []
    assert "task_assignments" in project


def test_create_project_allows_custom_notes():
    project = create_project(
        project_id="VTEST",
        name="Testprojekt",
        notes="Oprettet via Roerbot.",
    )

    assert project["notes"] == "Oprettet via Roerbot."
