from datetime import date

from projektstyring.backend.calendar_loader import load_calendars


calendars = load_calendars("projektstyring/data/calendars.json")

for calendar in calendars.values():
    print(calendar.id, calendar.name)

    for test_date in [
        date(2026, 6, 15),  # mandag
        date(2026, 6, 18),  # torsdag
        date(2026, 6, 19),  # fredag
        date(2026, 6, 20),  # lørdag
    ]:
        print(
            test_date,
            calendar.is_working_day(test_date),
            calendar.working_hours(test_date),
        )

    print()
