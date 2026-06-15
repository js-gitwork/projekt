from datetime import date, timedelta
from typing import List

from .models import Installation, Aktivitet
from .capacity_engine import CapacityEngine


class MultiScheduleEngine:
    def __init__(self, hold_map: dict, globale_helligdage=None, ferieperioder=None):
        self.hold_map = hold_map
        self.globale_helligdage = globale_helligdage or []
        self.ferieperioder = ferieperioder or []
        self.capacity = CapacityEngine(hold_map)
        self.hold_available_from = {}

    def planlæg(self, installationer: List[Installation]) -> List[Aktivitet]:
        alle_aktiviteter = []

        installationer = sorted(
            installationer,
            key=lambda inst: self._hovedledning_start(inst)
        )

        for installation in installationer:
            sidste_slut = None

            for aktivitet in installation.aktiviteter:
                if self._skal_springes_over(aktivitet):
                    continue

                hold = self.hold_map.get(aktivitet.hold)
                if not hold:
                    raise Exception(f"Ukendt hold: {aktivitet.hold}")

                if aktivitet.type == "hovedledning":
                    if not aktivitet.start_dato:
                        raise Exception(f"Hovedledning mangler låst dato på inst {installation.id}")

                    aktivitet.slut_dato = aktivitet.start_dato
                    self.hold_available_from[aktivitet.hold] = aktivitet.slut_dato + timedelta(days=1)
                    sidste_slut = aktivitet.slut_dato
                    alle_aktiviteter.append(aktivitet)
                    continue

                if sidste_slut:
                    tidligste_start = sidste_slut + timedelta(days=1)
                else:
                    tidligste_start = date.today()

                hold_start = self.hold_available_from.get(aktivitet.hold)
                if hold_start:
                    tidligste_start = max(tidligste_start, hold_start)

                tidligste_start = self._næste_arbejdsdag(tidligste_start, hold)

                aktivitet.start_dato = tidligste_start

                varighed = self.capacity.beregn_varighed(aktivitet)

                aktivitet.slut_dato = self._beregn_slutdato(
                    start=aktivitet.start_dato,
                    varighed=varighed,
                    hold=hold
                )

                self.hold_available_from[aktivitet.hold] = aktivitet.slut_dato + timedelta(days=1)
                sidste_slut = aktivitet.slut_dato
                alle_aktiviteter.append(aktivitet)

        return alle_aktiviteter

    def _skal_springes_over(self, aktivitet: Aktivitet) -> bool:
        if aktivitet.type in ["stikforberedelse", "stik", "kontrol", "korthat"]:
            return aktivitet.antal_stik == 0
        return False

    def _hovedledning_start(self, installation: Installation):
        for a in installation.aktiviteter:
            if a.type == "hovedledning" and a.start_dato:
                return a.start_dato
        return date.max

    def _er_ferie(self, dato: date) -> bool:
        for start, slut in self.ferieperioder:
            if start <= dato <= slut:
                return True
        return False

    def _er_arbejdsdag(self, dato: date, hold) -> bool:
        if dato in self.globale_helligdage:
            return False

        if self._er_ferie(dato):
            return False

        if hasattr(hold, "arbejdsdage"):
            weekday_map = {
                0: "man",
                1: "tir",
                2: "ons",
                3: "tor",
                4: "fre",
                5: "lør",
                6: "søn",
            }
            return weekday_map[dato.weekday()] in hold.arbejdsdage

        return dato.weekday() < 5

    def _næste_arbejdsdag(self, dato: date, hold) -> date:
        current = dato
        while not self._er_arbejdsdag(current, hold):
            current += timedelta(days=1)
        return current

    def _beregn_slutdato(self, start: date, varighed: int, hold) -> date:
        dage = 0
        current = start

        while dage < varighed:
            if self._er_arbejdsdag(current, hold):
                dage += 1
            current += timedelta(days=1)

        return current - timedelta(days=1)

    def print_plan(self, aktiviteter: List[Aktivitet]):
        print("\n📅 Multi-installation plan")
        print("-" * 80)

        for a in sorted(aktiviteter, key=lambda x: (x.start_dato, x.hold, x.installation_id)):
            print(
                f"{a.start_dato} → {a.slut_dato} | "
                f"{a.hold:8} | "
                f"Inst {a.installation_id:8} | "
                f"{a.type}"
            )
