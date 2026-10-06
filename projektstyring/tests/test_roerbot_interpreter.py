from projektstyring.backend.roerbot_interpreter import (
    normalize_data_requests,
)


def test_projects_installations_field_becomes_installations_resource():
    scope = {
        "project_ids": ["V165460"],
        "installation_ids": [],
        "team_ids": [],
    }

    raw_requests = [
        {
            "resource": "projects",
            "filters": [
                {
                    "field": "id",
                    "operator": "equals",
                    "value": "V165460",
                }
            ],
            "fields": ["installations"],
            "sort": None,
            "limit": None,
        }
    ]

    result = normalize_data_requests(
        raw_requests,
        scope=scope,
    )

    assert result == [
        {
            "resource": "installations",
            "filters": [
                {
                    "field": "project_id",
                    "operator": "equals",
                    "value": "V165460",
                }
            ],
            "fields": [],
            "sort": None,
            "limit": None,
        }
    ]
