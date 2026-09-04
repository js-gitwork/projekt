from sqlalchemy import select

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import (
    ProductionGroup,
    ProductionGroupTaskType,
    ProductionGroupWorkType,
)


PRODUCTION_GROUPS = [
    {
        "id": "stikarbejde",
        "name": "Stikarbejde",
        "description": (
            "Samlet produktionsgruppe for arbejde på stik, "
            "herunder langhat, korthat, brøndskud og "
            "punktreparationer."
        ),
        "task_types": [
            ("stik", 10),
            ("korthat", 20),
        ],
        "work_types": [
            ("langhat", 10),
            ("korthat", 20),
            ("broendskud", 30),
            ("pkt_rep", 40),
        ],
    },
    {
        "id": "korthatarbejde",
        "name": "Korthatarbejde",
        "description": (
            "Arbejder der produktionsmæssigt udføres sammen "
            "med korthatarbejdet."
        ),
        "task_types": [
            ("korthat", 10),
        ],
        "work_types": [
            ("korthat", 10),
            ("pkt_rep", 20),
        ],
    },
]


def seed_production_groups() -> int:
    created = 0

    with SessionLocal() as session:
        for item in PRODUCTION_GROUPS:
            group = session.scalar(
                select(ProductionGroup).where(
                    ProductionGroup.id == item["id"]
                )
            )

            if group is None:
                group = ProductionGroup(
                    id=item["id"],
                    name=item["name"],
                    description=item["description"],
                    active=True,
                )
                session.add(group)
                session.flush()
                created += 1
            else:
                group.name = item["name"]
                group.description = item["description"]
                group.active = True

            for task_type_id, sequence in item["task_types"]:
                member = session.scalar(
                    select(ProductionGroupTaskType).where(
                        ProductionGroupTaskType.production_group_id
                        == group.id,
                        ProductionGroupTaskType.task_type_id
                        == task_type_id,
                    )
                )

                if member is None:
                    session.add(
                        ProductionGroupTaskType(
                            production_group_id=group.id,
                            task_type_id=task_type_id,
                            sequence=sequence,
                            active=True,
                        )
                    )
                else:
                    member.sequence = sequence
                    member.active = True

            for work_type, sequence in item["work_types"]:
                member = session.scalar(
                    select(ProductionGroupWorkType).where(
                        ProductionGroupWorkType.production_group_id
                        == group.id,
                        ProductionGroupWorkType.work_type
                        == work_type,
                    )
                )

                if member is None:
                    session.add(
                        ProductionGroupWorkType(
                            production_group_id=group.id,
                            work_type=work_type,
                            sequence=sequence,
                            active=True,
                        )
                    )
                else:
                    member.sequence = sequence
                    member.active = True

        session.commit()

    return created


if __name__ == "__main__":
    created = seed_production_groups()
    print(f"Produktionsgrupper oprettet: {created}")