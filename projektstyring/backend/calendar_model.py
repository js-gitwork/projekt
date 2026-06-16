from dataclasses import dataclass, field
from datetime import date, time


@dataclass
class WorkDayRule:
    weekday: int
    start_time: time
    end_time: time

    def hours(self) -> float:
        delta_hours = (
            self.end_time.hour
            + self.end_time.minute / 60
            - self.start_time.hour
            - self.start_time.minute / 60
        )
        return delta_hours


@dataclass
class TeamCalendar:
    id: str
    name: str
    workdays: list[WorkDayRule] = field(default_factory=list)
    holidays: list[date] = field(default_factory=list)

    def rules_for_weekday(self, weekday: int) -> list[WorkDayRule]:
        return [
            rule
            for rule in self.workdays
            if rule.weekday == weekday
        ]

    def is_working_day(self, current_date: date) -> bool:
        if current_date in self.holidays:
            return False

        return bool(
            self.rules_for_weekday(
                current_date.weekday()
            )
        )

    def working_hours(self, current_date: date) -> float:
        if current_date in self.holidays:
            return 0

        return sum(
            rule.hours()
            for rule in self.rules_for_weekday(
                current_date.weekday()
            )
        )
