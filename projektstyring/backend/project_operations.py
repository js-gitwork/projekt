def set_installation_count(project: dict, count: int) -> dict:
    installations = project.get("installations", [])

    current_count = len(installations)

    if count > current_count:
        for number in range(current_count + 1, count + 1):
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

    elif count < current_count:
        installations = installations[:count]

    project["installations"] = installations

    return project
