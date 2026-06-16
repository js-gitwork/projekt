from datetime import date, timedelta

from projektstyring.backend.constraint_model import (
    ProjectConstraint,
    ConstraintType,
    ConstraintSeverity,
)


constraint = ProjectConstraint(
    id="c1",
    project_id="V165460",
    type=ConstraintType.EQUIPMENT_FAILURE,
    description="STIK2 bil nedbrudt",
    start_date=date.today(),
    end_date=date.today() + timedelta(days=4),
    affected_teams=["STIK2"],
    severity=ConstraintSeverity.HIGH,
    source="ai",
)

print(constraint)
print(constraint.label())
print("Rammes STIK2?", constraint.affects_team("STIK2"))
print("Rammes TV22?", constraint.affects_team("TV22"))
print("Aktiv i dag?", constraint.is_active_on(date.today()))
