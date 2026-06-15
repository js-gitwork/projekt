from datetime import date
from projektstyring.backend.zone_checker import ZoneChecker


checker = ZoneChecker("projektstyring/data/projects/V165460_zoner.json")

checker.print_overview()

tests = [
    ("5", date(2026, 7, 1)),
    ("5", date(2026, 8, 3)),
    ("13", date(2026, 7, 8)),
    ("13", date(2026, 7, 6)),
    ("2", date(2026, 7, 1)),
]

print("\n🔎 Adgangstest")
print("-" * 80)

for inst, dato in tests:
    result = checker.is_installation_accessible(inst, dato)
    print(
        f"Inst {inst} på {dato}: "
        f"{'OK' if result['accessible'] else 'IKKE ADGANG'} "
        f"- {result['reason']}"
    )
