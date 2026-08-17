from __future__ import annotations

from math import ceil


class CapacityEngine:
    def __init__(
        self,
        hold_map: dict,
    ):
        self.hold_map = hold_map

    def beregn_varighed(
        self,
        aktivitet,
    ) -> int:
        """
        Beregner aktivitetens varighed ud fra
        holdets registrerede kapacitet.

        Kapacitet kommer fra databasen via TeamRepository.
        Der findes ingen hardcodede holdkapaciteter her.
        """

        hold = self.hold_map.get(
            aktivitet.hold
        )

        if not hold:
            raise ValueError(
                f"Ukendt hold: "
                f"{aktivitet.hold}"
            )

        task_type = str(
            aktivitet.type
        )

        if task_type == "dtvk":
            return self._beregn_dtvk(
                aktivitet,
                hold,
            )

        if task_type in {
            "stik",
            "stikforberedelse",
            "kontrol",
        }:
            return self._beregn_quantity(
                quantity=getattr(
                    aktivitet,
                    "antal_stik",
                    0,
                ),
                capacity=hold.capacity_for(
                    task_type,
                    "stik",
                ),
            )

        if task_type == "broend":
            return self._beregn_quantity(
                quantity=getattr(
                    aktivitet,
                    "antal_brønde",
                    0,
                ),
                capacity=hold.capacity_for(
                    task_type,
                    "broende",
                ),
            )

        # Aktiviteter uden registreret
        # mængdebaseret kapacitet er foreløbig
        # én planlagt arbejdsdag.
        return 1

    def _beregn_dtvk(
        self,
        aktivitet,
        hold,
    ) -> int:
        meter = float(
            getattr(
                aktivitet,
                "hovedledning_meter",
                0,
            )
            or 0
        )

        stik = int(
            getattr(
                aktivitet,
                "antal_stik",
                0,
            )
            or 0
        )

        meter_capacity = (
            hold.capacity_for(
                "dtvk",
                "hovedledning_meter",
            )
        )

        stik_capacity = (
            hold.capacity_for(
                "dtvk",
                "stik",
            )
        )

        days = []

        if meter > 0:
            if meter_capacity <= 0:
                raise ValueError(
                    f"Holdet '{hold.id}' mangler "
                    "DTVK-kapacitet for "
                    "hovedledning_meter."
                )

            days.append(
                meter
                / meter_capacity
            )

        if stik > 0:
            if stik_capacity <= 0:
                raise ValueError(
                    f"Holdet '{hold.id}' mangler "
                    "DTVK-kapacitet for stik."
                )

            days.append(
                stik
                / stik_capacity
            )

        if not days:
            return 1

        return max(
            1,
            ceil(
                max(days)
            ),
        )

    @staticmethod
    def _beregn_quantity(
        *,
        quantity,
        capacity: float,
    ) -> int:
        amount = float(
            quantity
            or 0
        )

        if amount <= 0:
            return 1

        if capacity <= 0:
            raise ValueError(
                "Aktiviteten har en mængde, "
                "men holdet mangler registreret "
                "kapacitet for denne opgavetype."
            )

        return max(
            1,
            ceil(
                amount
                / capacity
            ),
        )