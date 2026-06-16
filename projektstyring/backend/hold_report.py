from dataclasses import dataclass, field


@dataclass
class HoldActivity:
    hold: str
    installation_id: int | None
    aktivitetstype: str
    start_dato: object
    slut_dato: object
    kilde: str = "plan"
    zone: str | None = None


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
            installation_text = (
                f"Inst {aktivitet.installation_id:8}"
                if aktivitet.installation_id is not None
                else "Inst ukendt "
            )

            zone_text = f" | Zone: {aktivitet.zone}" if aktivitet.zone else ""

            print(
                f"{aktivitet.start_dato} → {aktivitet.slut_dato} | "
                f"{installation_text} | "
                f"{aktivitet.aktivitetstype:18} | "
                f"{aktivitet.kilde}{zone_text}"
            )


class HoldReportGenerator:
    def generate(self, planning_report):
        reports = {}

        # Almindelige planlagte aktiviteter
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
                    kilde="plan",
                )
            )

        # Aktiviteter fra genåbningsplaner
        for reopen_schedule in planning_report.reopen_schedules:
            for aktivitet in reopen_schedule.activities:
                hold = aktivitet.hold

                if hold not in reports:
                    reports[hold] = HoldReport(hold)

                reports[hold].aktiviteter.append(
                    HoldActivity(
                        hold=hold,
                        installation_id=None,
                        aktivitetstype=aktivitet.task_type,
                        start_dato=aktivitet.start_dato,
                        slut_dato=aktivitet.slut_dato,
                        kilde="genåbning",
                        zone=aktivitet.zone,
                    )
                )

        return list(reports.values())
