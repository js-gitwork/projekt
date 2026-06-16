from projektstyring.backend.project_writer import save_project


project = {
    "id": "V999999",
    "name": "Testprojekt",
    "start_date": "2026-08-01",
    "installations": [
        {
            "id": "1",
            "sequence": 1,
            "expected_stik": 5,
            "hoveddato": None,
            "langhatte": None,
            "korthatte": None,
            "broende": 0,
            "notes": "",
        }
    ],
}

filename = save_project(project)

print("Gemt:", filename)
