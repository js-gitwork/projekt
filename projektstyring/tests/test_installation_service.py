import pytest

from projektstyring.backend.installation_service import (
    create_installations,
    default_installation,
)


def test_default_installation():
    installation = default_installation(1)

    assert installation["id"] == 1
    assert installation["active"] is True
    assert installation["hoveddato"] == ""
    assert installation["expected_stik"] == 0
    assert installation["active_stik"] == 0


def test_create_installations():
    project = {"id": "VTEST", "installations": []}

    create_installations(project, 3)

    assert len(project["installations"]) == 3
    assert project["installations"][0]["id"] == 1
    assert project["installations"][2]["id"] == 3


def test_create_installations_replaces_existing_installations():
    project = {
        "id": "VTEST",
        "installations": [default_installation(99)],
    }

    create_installations(project, 2)

    assert [item["id"] for item in project["installations"]] == [1, 2]


def test_create_installations_rejects_negative_count():
    project = {"id": "VTEST", "installations": []}

    with pytest.raises(ValueError):
        create_installations(project, -1)
