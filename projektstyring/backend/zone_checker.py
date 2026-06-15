import json
from datetime import date, timedelta
from pathlib import Path


class ZoneChecker:
    def __init__(self, zone_file):
        self.zone_file = Path(zone_file)
        self.zoner = self._load_zoner()

    def _load_zoner(self):
        with open(self.zone_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["zoner"]

    def find_zone_for_installation(self, installation_id):
        installation_id = str(installation_id)

        for zone in self.zoner:
            if installation_id in zone["installationer"]:
                return zone

        return None

    def is_installation_accessible(self, installation_id, dato: date):
        zone = self.find_zone_for_installation(installation_id)

        if not zone:
            return {
                "accessible": True,
                "reason": "Ingen afspærringszone tilknyttet installationen.",
                "zone": None
            }

        start = date.fromisoformat(zone["start_dato"])
        slut = date.fromisoformat(zone["slut_dato"])

        accessible = start <= dato <= slut

        return {
            "accessible": accessible,
            "reason": (
                f"Installation {installation_id} ligger i {zone['navn']} "
                f"({start} til {slut})."
            ),
            "zone": zone
        }

    def permit_deadline(self, zone_id):
        zone = self._find_zone_by_id(zone_id)

        if not zone:
            return None

        start = date.fromisoformat(zone["start_dato"])
        dage = zone.get("raadighedstilladelse_dage_foer", 28)

        return start - timedelta(days=dage)

    def warning_deadline(self, zone_id):
        zone = self._find_zone_by_id(zone_id)

        if not zone:
            return None

        start = date.fromisoformat(zone["start_dato"])
        timer = zone.get("beboervarsling_timer_foer", 48)

        return start - timedelta(hours=timer)

    def _find_zone_by_id(self, zone_id):
        for zone in self.zoner:
            if zone["id"] == zone_id:
                return zone
        return None

    def print_overview(self):
        print("\n🚧 Afspærringszoner")
        print("-" * 80)

        for zone in self.zoner:
            print(f"{zone['id']} | {zone['navn']}")
            print(f"  Installationer: {', '.join(zone['installationer'])}")
            print(f"  Periode:        {zone['start_dato']} → {zone['slut_dato']}")
            print(f"  Presniveau:     {zone['presniveau']}")
            print(f"  Tilladelse senest: {self.permit_deadline(zone['id'])}")
            print(f"  Varsling senest:   {self.warning_deadline(zone['id'])}")
