from dataclasses import dataclass, field
from collections import defaultdict
from datetime import date, timedelta


@dataclass
class ResourceMonth:
    hold: str
    year: int
    month: int
    available_days: int = 0
    booked_days: int = 0

    @property
    def utilization_percent(self) -> float:
        if self.available_days == 0:
            return 0.0

        return round((self.booked_days / self.available_days) * 100, 1)


@dataclass
class ResourceReport:
    months: list[ResourceMonth] = field(default_factory=list)

    def print_summary(self):
        print("\n📈 Holdbelægning pr. måned")
        print("-" * 80)

        for item in sorted(
            self.months,
            key=lambda x: (x.hold, x.year, x.month)
        ):
            print(
                f"{item.hold:8} | "
                f"{item.year}-{item.month:02d} | "
                f"Ledige arbejdsdage: {item.available_days:3} | "
                f"Bookede dage: {item.booked_days:3} | "
                f"Belægning: {item.utilization_percent:5.1f}%"
            )


class ResourceReportGenerator:
    def __init__(
        self,
        hold_map: dict,
        globale_helligdage=None,
        ferieperioder=None,
    ):
        self.hold_map = hold_map
        self.globale_helligdage = globale_helligdage or []
        self.ferieperioder = ferieperioder or []

    def generate(self, planning_report) -> ResourceReport:
        booked = defaultdict(set)

        for aktivitet in planning_report.schedule_result.activities:
            hold_name = aktivitet.hold

            if not aktivitet.start_dato or not aktivitet.slut_dato:
                continue

            current = aktivitet.start_dato

            while current <= aktivitet.slut_dato:
                booked[(hold_name, current.year, current.month)].add(current)
                current += timedelta(days=1)

        months = []

        for key, booked_dates in booked.items():
            hold_name, year, month = key
            hold = self.hold_map.get(hold_name)

            if not hold:
                continue

            available_days = self._available_days_in_month(
                year=year,
                month=month,
                hold=hold,
            )

            months.append(
                ResourceMonth(
                    hold=hold_name,
                    year=year,
                    month=month,
                    available_days=available_days,
                    booked_days=len(booked_dates),
                )
            )

        return ResourceReport(months=months)

    def _available_days_in_month(self, year: int, month: int, hold) -> int:
        current = date(year, month, 1)

        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)

        count = 0

        while current < next_month:
            if self._is_workday(current, hold):
                count += 1

            current += timedelta(days=1)

        return count

    def _is_vacation(self, dato: date) -> bool:
        for start, slut in self.ferieperioder:
            if start <= dato <= slut:
                return True

        return False

    def _is_workday(self, dato: date, hold) -> bool:
        if dato in self.globale_helligdage:
            return False

        if self._is_vacation(dato):
            return False

        weekday_map = {
            0: "man",
            1: "tir",
            2: "ons",
            3: "tor",
            4: "fre",
            5: "lør",
            6: "søn",
        }

        if hasattr(hold, "arbejdsdage"):
            return weekday_map[dato.weekday()] in hold.arbejdsdage

        return dato.weekday() < 5
