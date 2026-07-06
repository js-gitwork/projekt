from projektstyring.backend.baseline_service import create_baseline
from projektstyring.backend.decision_log import add_decision
from projektstyring.backend.roerbot_project_insight import (
    build_project_insight,
)
from projektstyring.backend.snapshot_service import add_snapshot


def make_project():
    return {
        "id": "VTEST",
        "status": "active",
        "installations": [
            {
                "id": 1,
                "active": True,
                "expected_stik": 4,
                "active_stik": 4,
                "langhatte": 4,
                "korthatte_extra": 0,
                "broende": 1,
                "notes": "",
            }
        ],
        "task_assignments": {},
    }


def test_build_project_insight():
    project = make_project()

    project["baseline"] = create_baseline(project)

    add_snapshot(project, reason="before_change")

    project["installations"][0]["active_stik"] = 5

    add_decision(
        project,
        decision_type="manual_change",
        reason="Projektleder rettede antal stik.",
    )

    insight = build_project_insight(project)

    assert insight["project_id"] == "VTEST"
    assert insight["status"] == "active"
    assert insight["has_baseline"] is True
    assert insight["decision_count"] == 1
    assert len(insight["changes_since_baseline"]) == 1
    assert len(insight["changes_since_latest_snapshot"]) == 1
