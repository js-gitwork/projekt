from dataclasses import dataclass, field
from math import ceil

from .rest_queue import RestQueue, RestQueueItem


@dataclass
class ReopenProposal:
    zone: str | None
    installation_ids: list[int] = field(default_factory=list)

    total_stik: int = 0
    total_brønde: int = 0

    estimated_days_stik: int = 0
    estimated_days_brønde: int = 0
    estimated_days_total: int = 0

    reason: str = ""

    def print_summary(self):
        zone_text = self.zone if self.zone else "ukendt zone"

        print("\n🚧 Forslag til genåbning")
        print("-" * 80)
        print(f"Zone: {zone_text}")
        print(f"Installationer: {', '.join(map(str, self.installation_ids))}")
        print(f"Rest stik: {self.total_stik}")
        print(f"Rest brønde: {self.total_brønde}")
        print(f"Estimeret varighed stik: {self.estimated_days_stik} dage")
        print(f"Estimeret varighed brønde: {self.estimated_days_brønde} dage")
        print(f"Estimeret samlet genåbning: {self.estimated_days_total} dage")
        print(f"Årsag: {self.reason}")


class ReopenPlanner:
    def __init__(
        self,
        stik_capacity_per_day: int = 5,
        brønd_capacity_per_day: int = 6,
        minimum_reopen_days: int = 1,
    ):
        self.stik_capacity_per_day = stik_capacity_per_day
        self.brønd_capacity_per_day = brønd_capacity_per_day
        self.minimum_reopen_days = minimum_reopen_days

    def create_proposals(self, rest_queue: RestQueue) -> list[ReopenProposal]:
        grouped = {}

        for item in rest_queue.items:
            key = item.zone

            if key not in grouped:
                grouped[key] = []

            grouped[key].append(item)

        proposals = []

        for zone, items in grouped.items():
            proposal = self._create_proposal_for_zone(zone, items)
            proposals.append(proposal)

        return proposals

    def _create_proposal_for_zone(
        self,
        zone: str | None,
        items: list[RestQueueItem],
    ) -> ReopenProposal:
        installation_ids = [item.installation_id for item in items]

        total_stik = sum(item.total_stik for item in items)
        total_brønde = sum(item.total_brønde for item in items)

        estimated_days_stik = 0
        if total_stik > 0:
            estimated_days_stik = ceil(total_stik / self.stik_capacity_per_day)

        estimated_days_brønde = 0
        if total_brønde > 0:
            estimated_days_brønde = ceil(total_brønde / self.brønd_capacity_per_day)

        estimated_days_total = max(
            self.minimum_reopen_days,
            estimated_days_stik,
            estimated_days_brønde,
        )

        return ReopenProposal(
            zone=zone,
            installation_ids=installation_ids,
            total_stik=total_stik,
            total_brønde=total_brønde,
            estimated_days_stik=estimated_days_stik,
            estimated_days_brønde=estimated_days_brønde,
            estimated_days_total=estimated_days_total,
            reason="Restarbejde kræver ny gyldig afspærringsperiode",
        )
