from projektstyring.backend.project_repository import (
    ProjectRepository,
)
from projektstyring.backend.snapshot_service import (
    create_snapshot,
    get_latest_snapshot,
    get_snapshot,
    list_snapshots,
)


PROJECT_ID = "V999999"


def test_create_and_get_snapshot():
    project = ProjectRepository().load_project(
        PROJECT_ID
    )

    created = create_snapshot(
        project_id=PROJECT_ID,
        project_state=project,
        reason="Testsnapshot",
        snapshot_type="test",
        phase="standalone",
    )

    loaded = get_snapshot(created["id"])

    assert loaded is not None
    assert loaded["id"] == created["id"]
    assert loaded["project_id"] == PROJECT_ID
    assert loaded["reason"] == "Testsnapshot"
    assert loaded["project_state"]["id"] == PROJECT_ID


def test_get_latest_snapshot():
    project = ProjectRepository().load_project(
        PROJECT_ID
    )

    created = create_snapshot(
        project_id=PROJECT_ID,
        project_state=project,
        reason="Seneste testsnapshot",
        snapshot_type="test_latest",
        phase="standalone",
    )

    latest = get_latest_snapshot(
        PROJECT_ID,
        snapshot_type="test_latest",
    )

    assert latest is not None
    assert latest["id"] == created["id"]


def test_list_snapshots():
    snapshots = list_snapshots(PROJECT_ID)

    assert isinstance(snapshots, list)

    for snapshot in snapshots:
        assert snapshot["project_id"] == PROJECT_ID