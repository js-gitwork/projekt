from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from projektstyring.backend.database.connection import (
    SessionLocal,
)
from projektstyring.backend.db_models import (
    ProductionGroup,
)


class ProductionGroupRepository:
    def list_groups(
        self,
        *,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as session:
            statement = (
                select(ProductionGroup)
                .options(
                    selectinload(
                        ProductionGroup.task_type_members
                    ),
                    selectinload(
                        ProductionGroup.work_type_members
                    ),
                )
                .order_by(
                    ProductionGroup.name
                )
            )

            if active_only:
                statement = statement.where(
                    ProductionGroup.active.is_(True)
                )

            database_groups = (
                session.scalars(
                    statement
                ).all()
            )

            return [
                self._to_dict(group)
                for group in database_groups
            ]

    def get_group(
        self,
        group_id: str,
    ) -> dict[str, Any]:
        with SessionLocal() as session:
            statement = (
                select(ProductionGroup)
                .where(
                    ProductionGroup.id
                    == group_id
                )
                .options(
                    selectinload(
                        ProductionGroup.task_type_members
                    ),
                    selectinload(
                        ProductionGroup.work_type_members
                    ),
                )
            )

            database_group = (
                session.scalar(
                    statement
                )
            )

            if database_group is None:
                raise KeyError(
                    "Produktionsgruppen "
                    f"'{group_id}' findes ikke."
                )

            return self._to_dict(
                database_group
            )

    def find_groups_for_task_type(
        self,
        task_type_id: str,
        *,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        groups = self.list_groups(
            active_only=active_only,
        )

        return [
            group
            for group in groups
            if task_type_id
            in group["task_types"]
        ]

    def find_groups_for_work_type(
        self,
        work_type: str,
        *,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        groups = self.list_groups(
            active_only=active_only,
        )

        return [
            group
            for group in groups
            if work_type
            in group["work_types"]
        ]

    @staticmethod
    def _to_dict(
        database_group: ProductionGroup,
    ) -> dict[str, Any]:
        task_members = sorted(
            (
                member
                for member
                in database_group.task_type_members
                if member.active
            ),
            key=lambda member: (
                member.sequence,
                member.task_type_id,
            ),
        )

        work_members = sorted(
            (
                member
                for member
                in database_group.work_type_members
                if member.active
            ),
            key=lambda member: (
                member.sequence,
                member.work_type,
            ),
        )

        return {
            "id": database_group.id,
            "name": database_group.name,
            "description": (
                database_group.description
            ),
            "active": database_group.active,
            "task_types": [
                member.task_type_id
                for member in task_members
            ],
            "work_types": [
                member.work_type
                for member in work_members
            ],
        }
