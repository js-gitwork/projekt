from projektstyring.backend.conversation_context import (
    clear_context,
    get_context,
    save_context,
)


def test_save_and_get_context():
    save_context(
        "test_user",
        {
            "topic": "projects",
            "filter": {"status": "active"},
            "project_ids": ["V1", "V2"],
        },
    )

    context = get_context("test_user")

    assert context["topic"] == "projects"
    assert context["project_ids"] == ["V1", "V2"]


def test_clear_context():
    save_context("test_user", {"topic": "projects"})

    clear_context("test_user")

    assert get_context("test_user") == {}


def test_missing_context_returns_empty_dict():
    assert get_context("unknown_user") == {}
