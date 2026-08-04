from sqlalchemy import select

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import TaskType


TASK_TYPES = [
    {
        "id": "forarbejde",
        "name": "Forarbejde",
        "category": "production",
        "standard_sequence": 10,
        "default_unit": "installation",
        "description": "Forberedende arbejde før hovedledning.",
    },
    {
        "id": "hovedledning",
        "name": "Hovedledning",
        "category": "production",
        "standard_sequence": 20,
        "default_unit": "installation",
        "description": "Installation af hovedliner på manuelt fastlagt dato.",
    },
    {
        "id": "stikforberedelse",
        "name": "Stikforberedelse",
        "category": "production",
        "standard_sequence": 30,
        "default_unit": "stik",
        "description": "Forberedelse af stik før installation.",
    },
    {
        "id": "stik",
        "name": "Stik",
        "category": "production",
        "standard_sequence": 40,
        "default_unit": "stik",
        "description": "Installation og genåbning af aktive stik.",
    },
    {
        "id": "kontrol",
        "name": "Kontrol",
        "category": "production",
        "standard_sequence": 50,
        "default_unit": "stik",
        "description": "Kontrol af udført stikarbejde.",
    },
    {
        "id": "korthat",
        "name": "Korthat",
        "category": "production",
        "standard_sequence": 60,
        "default_unit": "stik",
        "description": "Montering af korthatte.",
    },
    {
        "id": "broend",
        "name": "Brønd",
        "category": "production",
        "standard_sequence": 70,
        "default_unit": "brønd",
        "description": "Renovering af brønde.",
    },
    {
        "id": "dtvk",
        "name": "DTVK",
        "category": "production",
        "standard_sequence": 80,
        "default_unit": "installation",
        "description": "Afsluttende TV-kontrol og dokumentation.",
    },
    {
        "id": "broendscanning",
        "name": "Brøndscanning",
        "category": "production",
        "standard_sequence": 90,
        "default_unit": "brønd",
        "description": "Scanning af brønde.",
    },
]


def seed_task_types() -> int:
    created = 0

    with SessionLocal() as session:
        for item in TASK_TYPES:
            existing = session.scalar(
                select(TaskType).where(TaskType.id == item["id"])
            )

            if existing:
                existing.name = item["name"]
                existing.category = item["category"]
                existing.standard_sequence = item["standard_sequence"]
                existing.default_unit = item["default_unit"]
                existing.description = item["description"]
                existing.active = True
                continue

            session.add(
                TaskType(
                    **item,
                    active=True,
                )
            )
            created += 1

        session.commit()

    return created


if __name__ == "__main__":
    created = seed_task_types()
    print(f"Opgavetyper oprettet: {created}")
