from projektstyring.backend.project_loader import load_project_installations


installationer = load_project_installations(
    "projektstyring/data/projects/V165460_project.json"
)

for inst in installationer:
    print(inst.id, inst.projekt_id, inst.rækkefølge)

    for aktivitet in inst.aktiviteter:
        print(
            "Aktivitet:",
            aktivitet.id,
            "| Type:",
            aktivitet.type,
            "| Hold:",
            aktivitet.hold,
            "| Antal stik:",
            aktivitet.antal_stik,
            "| Start:",
            aktivitet.start_dato,
        )
