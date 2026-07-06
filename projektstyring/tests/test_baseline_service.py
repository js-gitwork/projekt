from projektstyring.backend.baseline_service import (
    create_baseline,
    has_baseline,
)


def test_create_baseline_copies_project_state():
    project = {
        "id": "VTEST",
        "status": "upcoming",
        "installations": [{"id": 1, "active_stik": 4}],
        "task_assignments": {"hovedledning": ["filt_oest"]},
    }

    baseline = create_baseline(project)

    assert baseline["project_id"] == "VTEST"
    assert baseline["status_at_creation"] == "upcoming"
    assert baseline["installations"][0]["active_stik"] == 4
    assert baseline["task_assignments"]["hovedledning"] == ["filt_oest"]


def test_create_baseline_uses_deepcopy():
    project = {
        "id": "VTEST",
        "status": "upcoming",
        "installations": [{"id": 1, "active_stik": 4}],
        "task_assignments": {},
    }

    baseline = create_baseline(project)

    project["installations"][0]["active_stik"] = 9

    assert baseline["installations"][0]["active_stik"] == 4


def test_has_baseline():
    assert has_baseline({"baseline": {"project_id": "VTEST"}}) is True
    assert has_baseline({"baseline": None}) is False
    assert has_baseline({}) is False
