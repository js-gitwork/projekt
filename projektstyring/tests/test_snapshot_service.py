from projektstyring.backend.snapshot_service import (
    add_snapshot,
    create_snapshot,
    get_latest_snapshot,
)


def make_project():
    return {
        "id": "VTEST",
        "status": "active",
        "installations": [{"id": 1, "active_stik": 4}],
        "task_assignments": {"hovedledning": ["filt_oest"]},
    }


def test_create_snapshot_copies_project_state():
    project = make_project()

    snapshot = create_snapshot(project, reason="before_plan_change")

    assert snapshot["project_id"] == "VTEST"
    assert snapshot["reason"] == "before_plan_change"
    assert snapshot["status"] == "active"
    assert snapshot["installations"][0]["active_stik"] == 4


def test_create_snapshot_uses_deepcopy():
    project = make_project()

    snapshot = create_snapshot(project)

    project["installations"][0]["active_stik"] = 9

    assert snapshot["installations"][0]["active_stik"] == 4


def test_add_snapshot():
    project = make_project()

    add_snapshot(project, reason="before_change")

    assert len(project["snapshots"]) == 1
    assert project["snapshots"][0]["reason"] == "before_change"


def test_get_latest_snapshot():
    project = make_project()

    add_snapshot(project, reason="first")
    add_snapshot(project, reason="second")

    latest = get_latest_snapshot(project)

    assert latest["reason"] == "second"


def test_get_latest_snapshot_returns_none_when_empty():
    assert get_latest_snapshot({}) is None
