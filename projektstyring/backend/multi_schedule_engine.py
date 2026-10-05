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
    ):
        self.hold_map = hold_map
        self.globale_helligdage = globale_helligdage or []
        self.ferieperioder = ferieperioder or []

        self.capacity = CapacityEngine(hold_map)

        # Næste ledige dato pr. hold
        self.hold_available_from = {}

    def planlæg(
        self,
        installationer: List[Installation],
    ) -> ScheduleResult:
        result = ScheduleResult()

        installationer = sorted(
            installationer,
            key=lambda inst: self._hovedledning_start(inst),
        )

        for installation in installationer:
            sidste_slut = None

            for aktivitet in installation.aktiviteter:
                if self._skal_springes_over(aktivitet):
                    continue

                hold = self.hold_map.get(
                    aktivitet.hold
                )

                if not hold:
                    result.add_rest_work(
                        installation_id=(
                            aktivitet.installation_id
                        ),
                        task_type=aktivitet.type,
                        reason=(
                            f"Ukendt hold: {aktivitet.hold}"
                        ),
                        quantity=(
                            self._antal_for_aktivitet(
                                aktivitet
                            )
                        ),
                        data={
                            "aktivitet": aktivitet
                        },
                    )

                    result.add_warning(
                        installation_id=(
                            aktivitet.installation_id
                        ),
                        message=(
                            f"Ukendt hold '{aktivitet.hold}' "
                            "på installation "
                            f"{aktivitet.installation_id}"
                        ),
                        severity="error",
                    )

                    continue

                # Hovedledning er låst til sin
                # planlagte dato.
                if aktivitet.type == "hovedledning":
                    if not aktivitet.start_dato:
                        result.add_rest_work(
                            installation_id=(
                                aktivitet.installation_id
                            ),
                            task_type=aktivitet.type,
                            reason=(
                                "Hovedledning mangler "
                                "låst startdato"
                            ),
                            quantity=(
                                self._antal_for_aktivitet(
                                    aktivitet
                                )
                            ),
                            data={
                                "aktivitet": aktivitet
                            },
                        )

                        result.add_warning(
                            installation_id=(
                                aktivitet.installation_id
                            ),
                            message=(
                                "Hovedledning mangler "
                                "låst dato på installation "
                                f"{aktivitet.installation_id}"
                            ),
                            severity="error",
                        )

                        continue

                    (
                        is_working_day,
                        calendar_reason,
                    ) = (
                        self._arbejdsdag_status(
                            aktivitet.start_dato,
                            hold,
                        )
                    )

                    if not is_working_day:
                        result.add_warning(
                            installation_id=(
                                aktivitet.installation_id
                            ),
                            message=(
                                f"Hovedledning på installation "
                                f"{aktivitet.installation_id} "
                                f"er låst til "
                                f"{aktivitet.start_dato}, men "
                                f"holdet '{aktivitet.hold}' "
                                "er ikke registreret som "
                                "tilgængeligt den dag"
                                + (
                                    f": {calendar_reason}"
                                    if calendar_reason
                                    else "."
                                )
                            ),
                            severity="warning",
                        )

                    aktivitet.slut_dato = (
                        aktivitet.start_dato
                    )

                    self.hold_available_from[
                        aktivitet.hold
                    ] = (
                        aktivitet.slut_dato
                        + timedelta(days=1)
                    )

                    sidste_slut = (
                        aktivitet.slut_dato
                    )

                    result.add_activity(
                        aktivitet
                    )

                    continue

                # Første mulige dato efter forrige
                # aktivitet på samme installation.
                if sidste_slut:
                    tidligste_start = (
                        sidste_slut
                        + timedelta(days=1)
                    )
                else:
                    tidligste_start = date.today()

                # Holdets kalender.
                hold_start = (
                    self.hold_available_from.get(
                        aktivitet.hold
                    )
                )

                if hold_start:
                    tidligste_start = max(
                        tidligste_start,
                        hold_start,
                    )

                # Find næste arbejdsdag for holdet.
                tidligste_start = (
                    self._næste_arbejdsdag(
                        tidligste_start,
                        hold,
                    )
                )

                aktivitet.start_dato = (
                    tidligste_start
                )

                varighed = (
                    self.capacity.beregn_varighed(
                        aktivitet
                    )
                )

                aktivitet.slut_dato = (
                    self._beregn_slutdato(
                        start=aktivitet.start_dato,
                        varighed=varighed,
                        hold=hold,
                    )
                )

                self.hold_available_from[
                    aktivitet.hold
                ] = (
                    aktivitet.slut_dato
                    + timedelta(days=1)
                )

                sidste_slut = (
                    aktivitet.slut_dato
                )

                result.add_activity(
                    aktivitet
                )

        return result

    def _antal_for_aktivitet(
        self,
        aktivitet: Aktivitet,
    ) -> int:
        if (
            hasattr(
                aktivitet,
                "antal_stik",
            )
            and aktivitet.antal_stik
        ):
            return aktivitet.antal_stik

        if (
            hasattr(
                aktivitet,
                "antal_brønde",
            )
            and aktivitet.antal_brønde
        ):
            return aktivitet.antal_brønde

        return 0

    def _skal_springes_over(
        self,
        aktivitet: Aktivitet,
    ) -> bool:
        if aktivitet.type in [
            "stikforberedelse",
            "stik",
            "kontrol",
            "korthat",
        ]:
            return aktivitet.antal_stik == 0

        return False

    def _hovedledning_start(
        self,
        installation: Installation,
    ):
        for aktivitet in (
            installation.aktiviteter
        ):
            if (
                aktivitet.type
                == "hovedledning"
                and aktivitet.start_dato
            ):
                return aktivitet.start_dato

        return date.max

    def _er_ferie(
        self,
        dato: date,
    ) -> bool:
        for start, slut in (
            self.ferieperioder
        ):
            if start <= dato <= slut:
                return True

        return False

    def _find_calendar_exception(
        self,
        dato: date,
        hold,
    ):
        """
        Finder den kalenderundtagelse, der gælder
        for holdet på den angivne dato.

        Holdspecifikke undtagelser har højere
        prioritet end kalenderbrede undtagelser.

        Hvis flere undtagelser af samme type
        overlapper, bruges den senest oprettede
        deterministisk via højeste id.
        """

        matches = []

        for exception in getattr(
            hold,
            "calendar_exceptions",
            [],
        ):
            date_from = exception.get(
                "date_from"
            )
            date_to = exception.get(
                "date_to"
            )

            if (
                date_from is None
                or date_to is None
            ):
                continue

            if not (
                date_from
                <= dato
                <= date_to
            ):
                continue

            matches.append(
                exception
            )

        if not matches:
            return None

        matches.sort(
            key=lambda exception: (
                0
                if exception.get("scope")
                == "team"
                else 1,
                -int(
                    exception.get("id")
                    or 0
                ),
            )
        )

        return matches[0]

    def _arbejdsdag_status(
        self,
        dato: date,
        hold,
    ) -> tuple[bool, str]:
        """
        Returnerer både arbejdsstatus og årsag.

        Kalenderundtagelser har højeste prioritet,
        fordi de netop kan ændre en normal
        arbejdsdag til fridag eller omvendt.
        """

        exception = (
            self._find_calendar_exception(
                dato,
                hold,
            )
        )

        if exception is not None:
            working = bool(
                exception.get(
                    "working"
                )
            )

            reason = str(
                exception.get("reason")
                or exception.get(
                    "exception_type"
                )
                or "kalenderundtagelse"
            ).strip()

            return (
                working,
                reason,
            )

        if dato in self.globale_helligdage:
            return (
                False,
                "global helligdag",
            )

        if self._er_ferie(dato):
            return (
                False,
                "ferieperiode",
            )

        if hold.working_days:
            if (
                dato.weekday()
                in hold.working_days
            ):
                return (
                    True,
                    "normal arbejdsdag",
                )

            return (
                False,
                "holdets normale arbejdsuge",
            )

        if dato.weekday() < 5:
            return (
                True,
                "normal arbejdsdag",
            )

        return (
            False,
            "weekend",
        )

    def _er_arbejdsdag(
        self,
        dato: date,
        hold,
    ) -> bool:
        working, _reason = (
            self._arbejdsdag_status(
                dato,
                hold,
            )
        )

        return working
        if dato in self.globale_helligdage:
            return False

        if self._er_ferie(dato):
            return False

        if hold.working_days:
            return (
        dato.weekday()
                in hold.working_days
            )

        return dato.weekday() < 5

    def _næste_arbejdsdag(
        self,
        dato: date,
        hold,
    ) -> date:
        current = dato

        while not self._er_arbejdsdag(
            current,
            hold,
        ):
            current += timedelta(days=1)

        return current

    def _beregn_slutdato(
        self,
        start: date,
        varighed: int,
        hold,
    ) -> date:
        dage = 0
        current = start

        while dage < varighed:
            if self._er_arbejdsdag(
                current,
                hold,
            ):
                dage += 1

            current += timedelta(days=1)

        return current - timedelta(days=1)

    def print_plan(
        self,
        result: ScheduleResult,
    ):
        print(
            "\n📅 Multi-installation plan"
        )
        print("-" * 80)

        for aktivitet in sorted(
            result.activities,
            key=lambda x: (
                x.start_dato,
                x.hold,
                x.installation_id,
            ),
        ):
            print(
                f"{aktivitet.start_dato} "
                f"→ {aktivitet.slut_dato} | "
                f"{aktivitet.hold:8} | "
                f"Inst "
                f"{aktivitet.installation_id:8} | "
                f"{aktivitet.type}"
            )

        if result.rest_work:
            print("\n🟡 Restarbejde")
            print("-" * 80)

            for rest in result.rest_work:
                print(
                    f"Inst "
                    f"{rest.installation_id:8} | "
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
                    f"Inst "
                    f"{warning.installation_id} | "
                    f"{warning.message}"
                )