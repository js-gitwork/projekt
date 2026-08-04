from __future__ import annotations

import json
from datetime import time
from pathlib import Path

from sqlalchemy import select

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import (
    WorkCalendar,
    WorkCalendarRule,
)


DEFAULT_CALENDAR_FILE = Path(
    "projektstyring/data/calendars.json"
)


def parse_time(value: str | None) -> time | None:
    if not value:
        return None

    return time.fromisoformat(value)


def seed_calendars(
    filename: Path = DEFAULT_CALENDAR_FILE,
) -> dict[str, int]:
    with filename.open("r", encoding="utf-8") as file:
        calendar_data = json.load(file)

    result = {
        "calendars_created": 0,
        "calendars_updated": 0,
        "rules_created": 0,
        "rules_updated": 0,
        "rules_deleted": 0,
    }

    with SessionLocal() as session:
        for item in calendar_data:
            calendar = session.get(
                WorkCalendar,
                str(item["id"]),
            )

            if calendar is None:
                calendar = WorkCalendar(
                    id=str(item["id"]),
                    name=str(item["name"]),
                )
                session.add(calendar)
                result["calendars_created"] += 1
            else:
                result["calendars_updated"] += 1

            calendar.name = str(item["name"])
            calendar.timezone_name = str(
                item.get("timezone_name")
                or "Europe/Copenhagen"
            )
            calendar.active = bool(
                item.get("active", True)
            )
            calendar.notes = str(
                item.get("notes") or ""
            )

            session.flush()

            existing_rules = {
                rule.weekday: rule
                for rule in session.scalars(
                    select(WorkCalendarRule).where(
                        WorkCalendarRule.calendar_id
                        == calendar.id
                    )
                )
            }

            imported_weekdays = set()

            for rule_data in item.get("rules", []):
                weekday = int(rule_data["weekday"])
                imported_weekdays.add(weekday)

                rule = existing_rules.get(weekday)

                if rule is None:
                    rule = WorkCalendarRule(
                        calendar_id=calendar.id,
                        weekday=weekday,
                    )
                    session.add(rule)
                    result["rules_created"] += 1
                else:
                    result["rules_updated"] += 1

                rule.working = bool(
                    rule_data.get("working", True)
                )
                rule.start_time = parse_time(
                    rule_data.get("start")
                )
                rule.end_time = parse_time(
                    rule_data.get("end")
                )

            for weekday, obsolete_rule in (
                existing_rules.items()
            ):
                if weekday not in imported_weekdays:
                    session.delete(obsolete_rule)
                    result["rules_deleted"] += 1

        session.commit()

    return result


if __name__ == "__main__":
    import_result = seed_calendars()

    print("Kalendere importeret:")
    for key, value in import_result.items():
        print(f"- {key}: {value}")
