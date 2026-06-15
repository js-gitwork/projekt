from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class RestWork:
    installation_id: int
    task_type: str
    quantity: int = 0
    zone: str | None = None
    reason: str = ""
    earliest_retry: date | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleWarning:
    installation_id: int | None
    message: str
    severity: str = "warning"


@dataclass
class ScheduleResult:
    activities: list[Any] = field(default_factory=list)
    rest_work: list[RestWork] = field(default_factory=list)
    warnings: list[ScheduleWarning] = field(default_factory=list)

    def add_activity(self, activity: Any):
        self.activities.append(activity)

    def add_rest_work(
        self,
        installation_id: int,
        task_type: str,
        reason: str,
        quantity: int = 0,
        zone: str | None = None,
        earliest_retry: date | None = None,
        data: dict[str, Any] | None = None,
    ):
        self.rest_work.append(
            RestWork(
                installation_id=installation_id,
                task_type=task_type,
                quantity=quantity,
                zone=zone,
                reason=reason,
                earliest_retry=earliest_retry,
                data=data or {},
            )
        )

    def add_warning(
        self,
        message: str,
        installation_id: int | None = None,
        severity: str = "warning",
    ):
        self.warnings.append(
            ScheduleWarning(
                installation_id=installation_id,
                message=message,
                severity=severity,
            )
        )
