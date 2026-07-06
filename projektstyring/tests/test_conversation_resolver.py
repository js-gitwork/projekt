from projektstyring.backend.conversation_resolver import (
    refers_to_previous_projects,
    resolve_project_reference,
)


def test_refers_to_previous_projects():
    assert refers_to_previous_projects("Hvad hedder de to projekter?")
    assert refers_to_previous_projects("Hvornår starter de?")
    assert refers_to_previous_projects("Hvad med dem begge?")


def test_does_not_refer_to_previous_projects():
    assert not refers_to_previous_projects("Hvor mange projekter er aktive?")


def test_resolve_project_reference_from_context():
    context = {
        "topic": "projects",
        "project_ids": ["V1", "V2"],
    }

    result = resolve_project_reference(
        "Hvad hedder de to projekter?",
        context,
    )

    assert result == {
        "type": "project_reference",
        "project_ids": ["V1", "V2"],
        "source": "last_context",
    }


def test_resolve_project_reference_returns_none_without_context():
    assert resolve_project_reference(
        "Hvad hedder de to?",
        {},
    ) is None
