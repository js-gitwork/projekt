from dataclasses import dataclass, field
from datetime import date, timedelta
from math import ceil

from .rest_queue import RestQueue, RestQueueItem


TASK_RULES = {
    "stikforberedelse": {
        "hold": "TV22",
        "capacity_per_day": 30,
        "unit": "stik",
        "order": 1,
    },
    "stik": {
        "hold": "STIK2",
        "capacity_per_day": 5,
        "unit": "stik",
        "order": 2,
    },
    "kontrol": {
        "hold": "TV22",
        "capacity_per_day": 30,
        "unit": "stik",
        "order": 3,
    },
    "korthat": {
        "hold": "HAT3",
        "capacity_per_day": 6,
        "unit": "stik",
        "order": 4,
    },
    "brønd": {
        "hold": "BRØND3",
        "capacity_per_day": 6,
        "unit": "brønde",
        "order": 5,
    },
    "brøndrenovering": {
        "hold": "BRØND3",
        "capacity_per_day": 6,
        "unit": "brønde",
        "order": 5,
    },
}


@dataclass
class ReopenTaskPlan:
    task_type: str
    hold: str
    quantity: int
    capacity_per_day: int
    estimated_days: int
    unit: str
    order: int


@dataclass
class ReopenProposal:
    zone: str | None
    installation_ids: list[int] = field(default_factory=list)

    task_plans: list[ReopenTaskPlan] = field(default_factory=list)

    total_stik: int = 0
    total_brønde: int = 0

    estimated_days_total: int = 0

    suggested_start: date | None = None
    suggested_end: date | None = None

    reason: str = ""

    def print_summary(self):
        zone_text = self.zone if self.zone else "ukendt zone"

        print("\n🚧 Forslag til genåbning")
        print("-" * 80)
        print(f"Zone: {zone_text}")
        print(f"Installationer: {', '.join(map(str, self.installation_ids))}")
        print(f"Rest stik: {self.total_stik}")
        print(f"Rest brønde: {self.total_brønde}")

        print("\nOpgaver i genåbningen:")
        for task in sorted(self.task_plans, key=lambda x: x.order):
            print(
                f"- {task.task_type:18} | "
                f"Hold: {task.hold:8} | "
                f"Antal: {task.quantity:4} {task.unit:6} | "
                f"Kapacitet: {task.capacity_per_day:4}/dag | "
                f"Varighed: {task.estimated_days} dag(e)"
            )

        print(f"\nEstimeret samlet genåbning: {self.estimated_days_total} arbejdsdage")

        if self.suggested_start and self.suggested_end:
            print(f"Foreslået periode: {self.suggested_start} → {self.suggested_end}")
        else:
            print("Foreslået periode: ikke beregnet")

        print(f"Årsag: {self.reason}")


class ReopenPlanner:
    def __init__(
        self,
        minimum_reopen_days: int = 1,
        globale_helligdage=None,
        ferieperioder=None,
    ):
        self.minimum_reopen_days = minimum_reopen_days
        self.globale_helligdage = globale_helligdage or []
        self.ferieperioder = ferieperioder or []

    def create_proposals(
        self,
        rest_queue: RestQueue,
        earliest_start: date | None = None,
    ) -> list[ReopenProposal]:
        grouped = {}

        for item in rest_queue.items:
            key = item.zone

            if key not in grouped:
                grouped[key] = []

            grouped[key].append(item)

        proposals = []

        for zone, items in grouped.items():
            proposal = self._create_proposal_for_zone(zone, items, earliest_start)
            proposals.append(proposal)

        return proposals

    def _create_proposal_for_zone(
        self,
        zone: str | None,
        items: list[RestQueueItem],
        earliest_start: date | None = None,
    ) -> ReopenProposal:
        installation_ids = [item.installation_id for item in items]

        task_quantities = {}

        for item in items:
            for rest in item.rest_work_items:
                task_type = rest.task_type

                if task_type not in TASK_RULES:
                    continue

                if task_type not in task_quantities:
                    task_quantities[task_type] = 0

                task_quantities[task_type] += rest.quantity

        task_plans = []

        for task_type, quantity in task_quantities.items():
            rule = TASK_RULES[task_type]

            estimated_days = ceil(quantity / rule["capacity_per_day"])

            task_plans.append(
                ReopenTaskPlan(
                    task_type=task_type,
                    hold=rule["hold"],
                    quantity=quantity,
                    capacity_per_day=rule["capacity_per_day"],
                    estimated_days=estimated_days,
                    unit=rule["unit"],
                    order=rule["order"],
                )
            )

        task_plans = sorted(task_plans, key=lambda x: x.order)

        total_stik = self._total_by_unit(task_plans, "stik")
        total_brønde = self._total_by_unit(task_plans, "brønde")

        estimated_days_total = max(
            self.minimum_reopen_days,
            sum(task.estimated_days for task in task_plans),
        )

        suggested_start = None
        suggested_end = None

        if earliest_start:
            suggested_start = self._next_workday(earliest_start)
            suggested_end = self._calculate_end_date(
                suggested_start,
                estimated_days_total,
            )

        return ReopenProposal(
            zone=zone,
            installation_ids=installation_ids,
            task_plans=task_plans,
            total_stik=total_stik,
            total_brønde=total_brønde,
            estimated_days_total=estimated_days_total,
            suggested_start=suggested_start,
            suggested_end=suggested_end,
            reason="Restarbejde kræver ny gyldig afspærringsperiode",
        )

    def _total_by_unit(self, task_plans: list[ReopenTaskPlan], unit: str) -> int:
        quantities = [
            task.quantity
            for task in task_plans
            if task.unit == unit
        ]

        if not quantities:
            return 0

        return max(quantities)

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
