from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ImportAction:
    entity_type: str
    action: str
    key: str


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
