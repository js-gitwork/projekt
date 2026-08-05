from projektstyring.backend.project_repository import (
    ProjectRepository,
)
from projektstyring.backend.roerbot_project_insight import (
    build_project_insight,
)


def test_build_project_insight_uses_database_history():
    project = ProjectRepository().load_project(
        "V999999"
    )

    insight = build_project_insight(project)

    assert insight["project_id"] == "V999999"
    assert insight["status"] == project["status"]
    assert isinstance(
        insight["changes_since_baseline"],
        list,
    )
    assert isinstance(
        insight[
            "changes_since_latest_snapshot"
        ],
        list,
    )
    assert isinstance(
        insight["decision_count"],
        int,
    )

    if insight["latest_decision"]:
        assert (
            insight["latest_decision"][
                "project_id"
            ]
            == "V999999"
        )