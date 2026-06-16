from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .schedule_result import ScheduleResult, RestWork


@dataclass
class RestQueueItem:
    installation_id: int
    zone: str | None = None

    total_stik: int = 0
    total_brønde: int = 0

    aktiviteter: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    rest_work_items: list[RestWork] = field(default_factory=list)

    def add_rest_work(self, rest: RestWork):
        if rest.task_type not in self.aktiviteter:
            self.aktiviteter.append(rest.task_type)

        if rest.reason and rest.reason not in self.reasons:
            self.reasons.append(rest.reason)

        self.rest_work_items.append(rest)

        if rest.task_type in [
            "stikforberedelse",
            "stik",
            "kontrol",
            "korthat",
        ]:
            self.total_stik = max(self.total_stik, rest.quantity)

        elif rest.task_type in [
            "brønd",
            "brøndrenovering",
        ]:
            self.total_brønde += rest.quantity


@dataclass
class RestQueue:
    items: list[RestQueueItem] = field(default_factory=list)

    def total_stik(self) -> int:
        return sum(item.total_stik for item in self.items)

    def total_brønde(self) -> int:
        return sum(item.total_brønde for item in self.items)

    def print_summary(self):
        print("\n🧺 Samlet restkø")
        print("-" * 80)

        if not self.items:
            print("Ingen restarbejde.")
            return

        for item in self.items:
            aktiviteter = ", ".join(item.aktiviteter)
            reasons = ", ".join(item.reasons)

            print(
                f"Inst {item.installation_id:8} | "
                f"Stik: {item.total_stik:4} | "
                f"Brønde: {item.total_brønde:4} | "
                f"Aktiviteter: {aktiviteter} | "
                f"Årsag: {reasons}"
            )

        print("-" * 80)
        print(
            f"Total rest: "
            f"{self.total_stik()} stik, "
            f"{self.total_brønde()} brønde"
        )


def aggregate_rest_work(result: ScheduleResult) -> RestQueue:
    grouped: Dict[Tuple[int, str | None], RestQueueItem] = {}

    for rest in result.rest_work:
        key = (rest.installation_id, rest.zone)

        if key not in grouped:
            grouped[key] = RestQueueItem(
                installation_id=rest.installation_id,
                zone=rest.zone,
            )

        grouped[key].add_rest_work(rest)

    return RestQueue(items=list(grouped.values()))
