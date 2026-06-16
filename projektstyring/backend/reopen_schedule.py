from dataclasses import dataclass
from datetime import date, timedelta

from .reopen_planner import ReopenProposal


@dataclass
class ReopenActivity:
    zone: str | None
    task_type: str
    hold: str
    start_dato: date
    slut_dato: date
    quantity: int
    unit: str


class ReopenSchedule:
    def __init__(self, activities: list[ReopenActivity]):
        self.activities = activities

    def print_summary(self):
        print("\n🛠️ Arbejdsplan for genåbning")
        print("-" * 80)

        if not self.activities:
            print("Ingen genåbningsaktiviteter.")
            return

        for activity in self.activities:
            zone_text = activity.zone if activity.zone else "ukendt zone"

            print(
                f"{activity.start_dato} → {activity.slut_dato} | "
                f"{activity.hold:8} | "
                f"{activity.task_type:18} | "
                f"{activity.quantity:4} {activity.unit:6} | "
                f"Zone: {zone_text}"
            )


class ReopenScheduleBuilder:
    def __init__(
        self,
        globale_helligdage=None,
        ferieperioder=None,
    ):
        self.globale_helligdage = globale_helligdage or []
        self.ferieperioder = ferieperioder or []

    def build(self, proposal: ReopenProposal) -> ReopenSchedule:
        activities = []

        if not proposal.suggested_start:
            return ReopenSchedule(activities)

        current = self._next_workday(proposal.suggested_start)

        for task in sorted(proposal.task_plans, key=lambda x: x.order):
            start = self._next_workday(current)
            end = self._calculate_end_date(start, task.estimated_days)

            activities.append(
                ReopenActivity(
                    zone=proposal.zone,
                    task_type=task.task_type,
                    hold=task.hold,
                    start_dato=start,
                    slut_dato=end,
                    quantity=task.quantity,
                    unit=task.unit,
                )
            )

            current = end + timedelta(days=1)

        return ReopenSchedule(activities)

    def _is_vacation(self, dato: date) -> bool:
        for start, slut in self.ferieperioder:
            if start <= dato <= slut:
                return True
        return False

    def _is_workday(self, dato: date) -> bool:
        if dato in self.globale_helligdage:
            return False

        if self._is_vacation(dato):
            return False

        return dato.weekday() < 5

    def _next_workday(self, dato: date) -> date:
        current = dato

        while not self._is_workday(current):
            current += timedelta(days=1)

        return current

    def _calculate_end_date(self, start: date, duration_days: int) -> date:
        days = 0
        current = start

        while days < duration_days:
            if self._is_workday(current):
                days += 1
            current += timedelta(days=1)

        return current - timedelta(days=1)
