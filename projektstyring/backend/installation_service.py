def default_installation(number):
    return {
        "id": number,
        "active": True,
        "hoveddato": "",
        "expected_stik": 0,
        "active_stik": 0,
        "langhatte": 0,
        "korthatte_extra": 0,
        "broende": 0,
        "notes": "",
    }


def create_installations(project, count):
    count = int(count)

    if count < 0:
        raise ValueError("Antal installationer kan ikke være negativt")

    project["installations"] = [
        default_installation(number)
        for number in range(1, count + 1)
    ]

    return project
