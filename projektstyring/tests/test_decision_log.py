from projektstyring.backend.decision_log import (
    add_decision,
    create_decision,
    get_decisions,
    get_latest_decision,
)


def test_create_decision():
    decision = create_decision(
        decision_type="project_started",
        reason="Projektleder har markeret projektet som startet.",
        trigger="user_action",
        affected_installations=[1, 2],
        metadata={"status": "active"},
    )

    assert decision["type"] == "project_started"
    assert decision["trigger"] == "user_action"
    assert decision["reason"] == "Projektleder har markeret projektet som startet."
    assert decision["affected_installations"] == [1, 2]
    assert decision["metadata"]["status"] == "active"


def test_add_decision():
    project = {"id": "VTEST"}

    add_decision(
        project,
        decision_type="survey_completed",
        reason="Survey er afsluttet og projektet er opdelt i installationer.",
        trigger="workflow",
        affected_installations=[1, 2, 3],
    )

    assert len(project["decisions"]) == 1
    assert project["decisions"][0]["type"] == "survey_completed"


def test_get_decisions_returns_empty_list():
    assert get_decisions({}) == []


def test_get_latest_decision():
    project = {"id": "VTEST"}

    add_decision(project, decision_type="first", reason="Første beslutning.")
    add_decision(project, decision_type="second", reason="Anden beslutning.")

    latest = get_latest_decision(project)

    assert latest["type"] == "second"
