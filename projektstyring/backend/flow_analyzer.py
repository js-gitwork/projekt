from dataclasses import dataclass, field
from datetime import timedelta


@dataclass
class FlowGap:
    installation_id: int
    from_task: str
    to_task: str
    from_end: object
    to_start: object
    waiting_days: int


@dataclass
class FlowBreak:
    installation_id: int
    task_type: str
    reason: str


@dataclass
class FlowAnalysis:
    gaps: list[FlowGap] = field(default_factory=list)
    breaks: list[FlowBreak] = field(default_factory=list)

    def print_summary(self):
        print("\n🌊 Flowanalyse")
        print("-" * 80)

        if not self.gaps and not self.breaks:
            print("Ingen flowproblemer fundet.")
            return

        if self.gaps:
            print("\nVentetid mellem aktiviteter:")
            for gap in sorted(
                self.gaps,
                key=lambda x: (x.installation_id, x.from_end)
            ):
                print(
                    f"Inst {gap.installation_id:8} | "
                    f"{gap.from_task:18} → {gap.to_task:18} | "
                    f"{gap.from_end} → {gap.to_start} | "
                    f"Ventetid: {gap.waiting_days} dag(e)"
                )

        if self.breaks:
            print("\nFlowbrud / ikke-planlagte aktiviteter:")
            for item in sorted(
                self.breaks,
                key=lambda x: (x.installation_id, x.task_type)
            ):
                print(
                    f"Inst {item.installation_id:8} | "
                    f"{item.task_type:18} | "
                    f"{item.reason}"
                )


class FlowAnalyzer:
    def analyze(self, planning_report) -> FlowAnalysis:
        analysis = FlowAnalysis()

        activities_by_installation = {}

        for activity in planning_report.schedule_result.activities:
            activities_by_installation.setdefault(
                activity.installation_id,
                []
            ).append(activity)

        for installation_id, activities in activities_by_installation.items():
            activities = sorted(
                activities,
                key=lambda x: x.start_dato
            )

            for previous, current in zip(activities, activities[1:]):
                if not previous.slut_dato or not current.start_dato:
                    continue

                waiting_days = (
                    current.start_dato - previous.slut_dato
                ).days - 1

                if waiting_days > 0:
                    analysis.gaps.append(
                        FlowGap(
                            installation_id=installation_id,
                            from_task=previous.type,
                            to_task=current.type,
                            from_end=previous.slut_dato,
                            to_start=current.start_dato,
                            waiting_days=waiting_days,
                        )
                    )

        for rest in planning_report.schedule_result.rest_work:
            analysis.breaks.append(
                FlowBreak(
                    installation_id=rest.installation_id,
                    task_type=rest.task_type,
                    reason=rest.reason,
                )
            )

        return analysis
