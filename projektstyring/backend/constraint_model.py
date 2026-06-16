from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class ConstraintType(str, Enum):
    EQUIPMENT_FAILURE = "equipment_failure"
    CREW_UNAVAILABLE = "crew_unavailable"
    AVAILABILITY_PERMISSION = "availability_permission"
    MATERIAL_DELAY = "material_delay"
    WEATHER = "weather"
    EXTERNAL_DEPENDENCY = "external_dependency"
    MANUAL_NOTE = "manual_note"


class ConstraintSeverity(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ProjectConstraint:
    id: str
    project_id: str
    type: ConstraintType
    description: str

    start_date: date | None = None
    end_date: date | None = None

    affected_teams: list[str] = field(default_factory=list)
    affected_installations: list[str] = field(default_factory=list)

    severity: ConstraintSeverity = ConstraintSeverity.NORMAL
    source: str = "manual"

    active: bool = True

    def affects_team(self, team: str) -> bool:
        return team in self.affected_teams

    def affects_installation(self, installation_id: str) -> bool:
        return installation_id in self.affected_installations

    def is_active_on(self, current_date: date) -> bool:
        if not self.active:
            return False

        if self.start_date and current_date < self.start_date:
            return False

        if self.end_date and current_date > self.end_date:
            return False

        return True

    def label(self) -> str:
        return CONSTRAINT_LABELS.get(
            self.type,
            self.type.value,
        )


CONSTRAINT_LABELS = {
    ConstraintType.EQUIPMENT_FAILURE: "Udstyrsnedbrud",
    ConstraintType.CREW_UNAVAILABLE: "Hold utilgængeligt",
    ConstraintType.AVAILABILITY_PERMISSION: "Rådighedstilladelse",
    ConstraintType.MATERIAL_DELAY: "Materialeforsinkelse",
    ConstraintType.WEATHER: "Vejr",
    ConstraintType.EXTERNAL_DEPENDENCY: "Ekstern afhængighed",
    ConstraintType.MANUAL_NOTE: "Manuel note",
}
