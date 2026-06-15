from datetime import date

from projektstyring.backend.zone_checker import ZoneChecker
from projektstyring.backend.zone_sequence import ZoneSequence


checker = ZoneChecker("projektstyring/data/projects/V165460_zoner.json")

sequence = ZoneSequence(
    "projektstyring/data/projects/V165460_zone_sequence.json",
    checker
)

sequence.print_overview()

tests = [
    ("5", date(2026, 7, 1)),
    ("13", date(2026, 7, 1)),
    ("13", date(2026, 7, 8)),
    ("5", date(2026, 7, 8)),
    ("5", date(2026, 8, 3)),
    ("13", date(2026, 8, 3)),
    ("2", date(2026, 7, 1)),
]

print("\n🔎 Aktiv front-test")
print("-" * 80)

for inst, dato in tests:
    result = sequence.installation_allowed_on(inst, dato)
    print(
        f"Inst {inst} på {dato}: "
        f"{'OK' if result['allowed'] else 'IKKE ADGANG'} - "
        f"{result['reason']}"
    )
