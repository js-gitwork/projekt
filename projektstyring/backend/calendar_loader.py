import json
from datetime import time

from projektstyring.backend.calendar_model import (
    TeamCalendar,
    WorkDayRule,
)


def parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def load_calendars(filename: str) -> dict[str, TeamCalendar]:
    with open(filename, "r", encoding="utf-8") as file:
        data = json.load(file)

    calendars = {}

    for item in data:
        rules = []

        for rule_data in item.get("rules", []):
            rules.append(
                WorkDayRule(
                    weekday=rule_data["weekday"],
                    start_time=parse_time(rule_data["start"]),
                    end_time=parse_time(rule_data["end"]),
                )
            )

        calendar = TeamCalendar(
            id=item["id"],
            name=item["name"],
            workdays=rules,
        )

        calendars[calendar.id] = calendar

    return calendars
