from dataclasses import dataclass, field


@dataclass
class Team:
    id: str
    name: str
    role: str
    calendar_id: str
    capacity_per_day: float = 0
    task_types: list[str] = field(default_factory=list)
    active: bool = True

    def can_do(self, task_type: str) -> bool:
        return task_type in self.task_types
