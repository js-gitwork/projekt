from dataclasses import dataclass, field


@dataclass
class HoldActivity:
    hold: str
    installation_id: int
    aktivitetstype: str
    start_dato: object
    slut_dato: object


@dataclass
class HoldReport:
    hold: str
    aktiviteter: list[HoldActivity] = field(default_factory=list)

    def print_summary(self):
        print(f"\n👷 Holdrapport: {self.hold}")
        print("-" * 80)

        for aktivitet in sorted(
            self.aktiviteter,
            key=lambda x: x.start_dato
        ):
            print(
                f"{aktivitet.start_dato} → {aktivitet.slut_dato} | "
                f"Inst {aktivitet.installation_id:8} | "
                f"{aktivitet.aktivitetstype}"
            )


class HoldReportGenerator:
    def generate(self, planning_report):
        reports = {}

        for aktivitet in planning_report.schedule_result.activities:
            hold = aktivitet.hold

            if hold not in reports:
                reports[hold] = HoldReport(hold)

            reports[hold].aktiviteter.append(
                HoldActivity(
                    hold=hold,
                    installation_id=aktivitet.installation_id,
                    aktivitetstype=aktivitet.type,
                    start_dato=aktivitet.start_dato,
                    slut_dato=aktivitet.slut_dato,
                )
            )

        return list(reports.values())
