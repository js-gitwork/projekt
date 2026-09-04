from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ImportAction:
    entity_type: str
    action: str
    key: str


@dataclass(slots=True)
class ImportConflict:
    entity_type: str
    key: str
    field: str

    existing_value: Any = None
    incoming_value: Any = None

    difference: float | None = None
    tolerance: float | None = None

    message: str = ""

    blocks_import: bool = True

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class ImportExecutionResult:
    project_id: str
    source: str

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    work_entries_created: int = 0

    actions: list[ImportAction] = field(
        default_factory=list
    )

    conflicts: list[ImportConflict] = field(
        default_factory=list
    )

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)

    @property
    def has_blocking_conflicts(self) -> bool:
        return any(
            conflict.blocks_import
            for conflict in self.conflicts
        )