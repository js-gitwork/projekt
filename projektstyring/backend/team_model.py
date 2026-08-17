from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Team:
    id: str
    name: str
    role: str
    calendar_id: str

    task_types: list[str] = field(
        default_factory=list
    )

    capacity_rates: dict[
        str,
        dict[str, float],
    ] = field(
        default_factory=dict
    )

    working_days: list[int] = field(
        default_factory=list
    )

    active: bool = True

    def can_do(
        self,
        task_type: str,
    ) -> bool:
        return task_type in self.task_types

    def capacity_for(
        self,
        task_type: str,
        quantity_type: str,
    ) -> float:
        task_rates = self.capacity_rates.get(
            task_type,
            {},
        )

        return float(
            task_rates.get(
                quantity_type,
                0.0,
            )
            or 0.0
        )