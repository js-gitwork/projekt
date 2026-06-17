def add_installations(
    project: dict,
    count: int,
) -> dict:
    installations = project.get(
        "installations",
        [],
    )

    current_count = len(
        installations
    )

    for number in range(
        current_count + 1,
        current_count + count + 1,
    ):
        installations.append(
            {
                "id": str(number),
                "sequence": number,
                "hoveddato": None,
                "expected_stik": 0,
                "langhatte": 0,
                "korthatte_extra": 0,
                "broende": 0,
                "notes": "",
            }
        )

    project["installations"] = installations

    return project
