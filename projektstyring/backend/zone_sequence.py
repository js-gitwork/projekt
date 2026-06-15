import json
from datetime import date
from pathlib import Path


class ZoneSequence:
    def __init__(self, sequence_file: str, zone_checker):
        self.sequence_file = Path(sequence_file)
        self.zone_checker = zone_checker
        self.sequence = self._load_sequence()

    def _load_sequence(self):
        with open(self.sequence_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["sequence"]

    def active_zone_on(self, dato: date):
        for item in self.sequence:
            start = date.fromisoformat(item["start_dato"])
            slut = item["slut_dato"]

            if slut is None:
                if dato >= start:
                    return item
            else:
                slut = date.fromisoformat(slut)
                if start <= dato <= slut:
                    return item

        return None

    def installation_allowed_on(self, installation_id: str, dato: date):
        active = self.active_zone_on(dato)

        if active is None:
            return {
                "allowed": False,
                "reason": "Ingen aktiv afspærringsfront på datoen.",
                "active_zone": None
            }

        zone = self.zone_checker.find_zone_for_installation(installation_id)

        if zone is None:
            return {
                "allowed": True,
                "reason": "Installation har ingen afspærringszone og kan planlægges frit.",
                "active_zone": active
            }

        allowed = zone["id"] == active["zone"]

        return {
            "allowed": allowed,
            "reason": (
                f"Installation {installation_id} ligger i zone {zone['id']}, "
                f"aktiv zone er {active['zone']}."
            ),
            "active_zone": active
        }

    def next_allowed_date(self, installation_id: str, from_date: date):
        current = from_date

        for _ in range(366):
            result = self.installation_allowed_on(installation_id, current)
            if result["allowed"]:
                return current
            current = current.replace()  # keep type stable
            from datetime import timedelta
            current = current + timedelta(days=1)

        return None

    def print_overview(self):
        print("\n🚧 Aktiv afspærringssekvens")
        print("-" * 80)

        for item in self.sequence:
            print(
                f"{item['zone']} | {item['navn']} | "
                f"{item['start_dato']} → {item['slut_dato'] or 'åben'}"
            )
