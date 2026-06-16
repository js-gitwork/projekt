from dataclasses import dataclass, field

from .schedule_result import ScheduleResult
from .rest_queue import RestQueue
from .reopen_planner import ReopenProposal
from .reopen_schedule import ReopenSchedule


@dataclass
class PlanningReport:
    schedule_result: ScheduleResult

    rest_queue: RestQueue | None = None

    reopen_proposals: list[ReopenProposal] = field(
        default_factory=list
    )

    reopen_schedules: list[ReopenSchedule] = field(
        default_factory=list
    )

    hold_reports: list = field(default_factory=list)

    resource_report: object | None = None

    def print_summary(self):
        print("\n📊 PLANRAPPORT")
        print("=" * 80)

        print(
            f"Planlagte aktiviteter : "
            f"{len(self.schedule_result.activities)}"
        )

        print(
            f"Restarbejder         : "
            f"{len(self.schedule_result.rest_work)}"
        )

        print(
            f"Advarsler            : "
            f"{len(self.schedule_result.warnings)}"
        )

        if self.rest_queue:
            print(
                f"Restkø installationer: "
                f"{len(self.rest_queue.items)}"
            )

            print(
                f"Samlet rest stik     : "
                f"{self.rest_queue.total_stik()}"
            )

            print(
                f"Samlet rest brønde   : "
                f"{self.rest_queue.total_brønde()}"
            )

        print(
            f"Genåbningsforslag    : "
            f"{len(self.reopen_proposals)}"
        )

        print(
            f"Genåbningsplaner     : "
            f"{len(self.reopen_schedules)}"
        )

        print(
            f"Holdrapporter        : "
            f"{len(self.hold_reports)}"
        )

        if self.resource_report:
            print(
                f"Ressourceperioder    : "
                f"{len(self.resource_report.months)}"
            )

        print("=" * 80)
