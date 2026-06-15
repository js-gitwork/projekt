from datetime import date, timedelta
from typing import List

from .models import Installation, Aktivitet
from .capacity_engine import CapacityEngine
from .schedule_result import ScheduleResult


class MultiScheduleEngine:
    def __init__(
        self,
        hold_map: dict,
        globale_helligdage=None,
        ferieperioder=None,
        zone_sequence=None
    ):
        self.hold_map = hold_map
        self.globale_helligdage = globale_helligdage or []
        self.ferieperioder = ferieperioder or []
        self.zone_sequence = zone_sequence

        self.capacity = CapacityEngine(hold_map)

        # Næste ledige dato pr. hold
        self.hold_available_from = {}

    def planlæg(self, installationer: List[Installation]) -> ScheduleResult:
        result = ScheduleResult()

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
                    result.add_rest_work(
                        installation_id=aktivitet.installation_id,
                        task_type=aktivitet.type,
                        reason=f"Ukendt hold: {aktivitet.hold}",
                        quantity=self._antal_for_aktivitet(aktivitet),
                        data={"aktivitet": aktivitet},
                    )
                    result.add_warning(
                        installation_id=aktivitet.installation_id,
                        message=f"Ukendt hold '{aktivitet.hold}' på installation {aktivitet.installation_id}",
                        severity="error",
                    )
                    continue

                # Hovedledning er låst til sin planlagte dato
                if aktivitet.type == "hovedledning":
                    if not aktivitet.start_dato:
                        result.add_rest_work(
                            installation_id=aktivitet.installation_id,
                            task_type=aktivitet.type,
                            reason="Hovedledning mangler låst startdato",
                            quantity=self._antal_for_aktivitet(aktivitet),
                            data={"aktivitet": aktivitet},
                        )
                        result.add_warning(
                            installation_id=aktivitet.installation_id,
                            message=f"Hovedledning mangler låst dato på installation {aktivitet.installation_id}",
                            severity="error",
                        )
                        continue

                    aktivitet.slut_dato = aktivitet.start_dato
                    self.hold_available_from[aktivitet.hold] = (
                        aktivitet.slut_dato + timedelta(days=1)
                    )
                    sidste_slut = aktivitet.slut_dato
                    result.add_activity(aktivitet)
                    continue

                # Første mulige dato efter forrige aktivitet på samme installation
                if sidste_slut:
                    tidligste_start = sidste_slut + timedelta(days=1)
                else:
                    tidligste_start = date.today()

                # Holdets kalender
                hold_start = self.hold_available_from.get(aktivitet.hold)
                if hold_start:
                    tidligste_start = max(tidligste_start, hold_start)

                # Find næste arbejdsdag for holdet
                tidligste_start = self._næste_arbejdsdag(tidligste_start, hold)

                # Zone-sekvens / aktiv afspærringsfront
                if self.zone_sequence:
                    zone_start = self.zone_sequence.next_allowed_date(
                        aktivitet.installation_id,
                        tidligste_start
                    )

                    if zone_start:
                        tidligste_start = self._næste_arbejdsdag(zone_start, hold)
                    else:
                        result.add_rest_work(
                            installation_id=aktivitet.installation_id,
                            task_type=aktivitet.type,
                            reason="Ingen gyldig afspærringsperiode fundet",
                            quantity=self._antal_for_aktivitet(aktivitet),
                            zone=getattr(aktivitet, "zone", None),
                            earliest_retry=tidligste_start,
                            data={"aktivitet": aktivitet},
                        )
                        result.add_warning(
                            installation_id=aktivitet.installation_id,
                            message=(
                                f"Installation {aktivitet.installation_id} kunne ikke planlægges "
                                f"for aktivitet '{aktivitet.type}' pga. manglende afspærringsperiode"
                            ),
                            severity="warning",
                        )
                        continue

                aktivitet.start_dato = tidligste_start

                varighed = self.capacity.beregn_varighed(aktivitet)

                aktivitet.slut_dato = self._beregn_slutdato(
                    start=aktivitet.start_dato,
                    varighed=varighed,
                    hold=hold
                )

                self.hold_available_from[aktivitet.hold] = (
                    aktivitet.slut_dato + timedelta(days=1)
                )

                sidste_slut = aktivitet.slut_dato
                result.add_activity(aktivitet)

        return result

    def _antal_for_aktivitet(self, aktivitet: Aktivitet) -> int:
        if hasattr(aktivitet, "antal_stik") and aktivitet.antal_stik:
            return aktivitet.antal_stik

        if hasattr(aktivitet, "antal_brønde") and aktivitet.antal_brønde:
            return aktivitet.antal_brønde

        return 0

    def _skal_springes_over(self, aktivitet: Aktivitet) -> bool:
        if aktivitet.type in ["stikforberedelse", "stik", "kontrol", "korthat"]:
            return aktivitet.antal_stik == 0
        return False

    def _hovedledning_start(self, installation: Installation):
        for aktivitet in installation.aktiviteter:
            if aktivitet.type == "hovedledning" and aktivitet.start_dato:
                return aktivitet.start_dato
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

    def print_plan(self, result: ScheduleResult):
        print("\n📅 Multi-installation plan")
        print("-" * 80)

        for aktivitet in sorted(
            result.activities,
            key=lambda x: (x.start_dato, x.hold, x.installation_id)
        ):
            print(
                f"{aktivitet.start_dato} → {aktivitet.slut_dato} | "
                f"{aktivitet.hold:8} | "
                f"Inst {aktivitet.installation_id:8} | "
                f"{aktivitet.type}"
            )

        if result.rest_work:
            print("\n🟡 Restarbejde")
            print("-" * 80)
            for rest in result.rest_work:
                print(
                    f"Inst {rest.installation_id:8} | "
                    f"{rest.task_type:18} | "
                    f"Antal: {rest.quantity:4} | "
                    f"{rest.reason}"
                )

        if result.warnings:
            print("\n⚠️ Advarsler")
            print("-" * 80)
            for warning in result.warnings:
                print(
                    f"{warning.severity.upper():8} | "
                    f"Inst {warning.installation_id} | "
                    f"{warning.message}"
                )
