from datetime import date, timedelta
from typing import List

from .models import Installation, Aktivitet
from .kalender import beregn_slutdato


# =========================
# 1. MAIN ENGINE
# =========================
class ScheduleEngine:

    def __init__(self, globale_helligdage: List[date]):
        self.globale_helligdage = globale_helligdage


    # =========================
    # 2. PLANLÆG INSTALLATION
    # =========================
    def planlæg_installation(self, installation: Installation, startdato: date, hold_map: dict):
        """
        Går igennem aktiviteter i rækkefølge og tildeler datoer
        """

        current_date = startdato

        for aktivitet in installation.aktiviteter:

            hold = hold_map.get(aktivitet.hold, None)

            if hold is None:
                raise Exception(f"Ukendt hold: {aktivitet.hold}")

            # Vent på afhængigheder (simpel version)
            if aktivitet.afhænger_af:
                # Find seneste slutdato blandt afhængigheder
                afhængighed_slut = self._find_afhængighed_slut(
                    installation.aktiviteter,
                    aktivitet.afhænger_af
                )
                if afhængighed_slut and afhængighed_slut > current_date:
                    current_date = afhængighed_slut + timedelta(days=1)

            # Beregn start
            aktivitet.start_dato = current_date

            # Beregn slut via kalender
            aktivitet.slut_dato = beregn_slutdato(
                start=current_date,
                varighed=aktivitet.varighed_dage,
                hold=hold,
                helligdage=self.globale_helligdage
            )

            # Næste aktivitet starter dagen efter
            current_date = aktivitet.slut_dato + timedelta(days=1)

        return installation


    # =========================
    # 3. FIND AFHÆNGIGHEDER
    # =========================
    def _find_afhængighed_slut(self, aktiviteter: List[Aktivitet], afhængigheder: List[str]):
        """
        Finder seneste slutdato blandt afhængigheder
        """
        slutdatoer = []

        for a in aktiviteter:
            if a.id in afhængigheder and a.slut_dato:
                slutdatoer.append(a.slut_dato)

        return max(slutdatoer) if slutdatoer else None


    # =========================
    # 4. DEBUG OUTPUT
    # =========================
    def print_schedule(self, installation: Installation):
        print(f"\n📅 Schedule for installation {installation.id}")
        print("-" * 50)

        for a in installation.aktiviteter:
            print(
                f"{a.type:20} | "
                f"{a.start_dato} → {a.slut_dato} | "
                f"hold: {a.hold}"
            )
