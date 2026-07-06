from projektstyring.backend.change_analyzer import (
    compare_installations,
    compare_states,
    compare_timeline,
)


def test_compare_installations_detects_changed_field():
    before = {
        "installations": [
            {"id": 1, "active_stik": 4},
        ],
    }

    after = {
        "installations": [
            {"id": 1, "active_stik": 5},
        ],
    }

    changes = compare_installations(before, after)

    assert changes == [
        {
            "type": "installation_changed",
            "installation_id": "1",
            "field": "active_stik",
            "before": 4,
            "after": 5,
        }
    ]


def test_compare_installations_detects_added_installation():
    before = {"installations": []}
    after = {"installations": [{"id": 1, "active_stik": 4}]}

    changes = compare_installations(before, after)

    assert changes[0]["type"] == "installation_added"
    assert changes[0]["installation_id"] == "1"


def test_compare_installations_detects_removed_installation():
    before = {"installations": [{"id": 1, "active_stik": 4}]}
    after = {"installations": []}

    changes = compare_installations(before, after)

    assert changes[0]["type"] == "installation_removed"
    assert changes[0]["installation_id"] == "1"


def test_compare_states():
    before = {
        "created_at": "2026-07-06T10:00:00",
        "project_id": "VTEST",
        "installations": [{"id": 1, "active_stik": 4}],
    }

    after = {
        "created_at": "2026-07-06T11:00:00",
        "project_id": "VTEST",
        "installations": [{"id": 1, "active_stik": 5}],
    }

    result = compare_states(before, after)

    assert result["project_id"] == "VTEST"
    assert len(result["installation_changes"]) == 1


def test_compare_timeline():
    states = [
        {
            "created_at": "1",
            "project_id": "VTEST",
            "installations": [{"id": 1, "active_stik": 4}],
        },
        {
            "created_at": "2",
            "project_id": "VTEST",
            "installations": [{"id": 1, "active_stik": 5}],
        },
        {
            "created_at": "3",
            "project_id": "VTEST",
            "installations": [{"id": 1, "active_stik": 6}],
        },
    ]

    timeline = compare_timeline(states)

    assert len(timeline) == 2
    assert timeline[0]["installation_changes"][0]["before"] == 4
    assert timeline[0]["installation_changes"][0]["after"] == 5
    assert timeline[1]["installation_changes"][0]["before"] == 5
    assert timeline[1]["installation_changes"][0]["after"] == 6
