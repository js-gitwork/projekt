from __future__ import annotations

from datetime import date
from typing import Any


class ProjectConstraintStatusService:
    """
    Beregner deterministisk status for projektconstraints.

    Servicen ændrer ingen data og gætter ikke på manglende
    oplysninger.

    For rådighedstilladelser gælder:

    - future:
      Startdato ligger efter vurderingsdatoen.

    - valid:
      Tilladelsen er startet, og slutdato ligger efter
      vurderingsdatoen.

    - expires_today:
      Slutdato er samme dato som vurderingsdatoen.
      Tilladelsen betragtes som gældende til og med slutdatoen.

    - expired:
      Slutdato ligger før vurderingsdatoen.

    - end_date_unknown:
      Tilladelsen er startet eller har ingen startdato,
      men der findes ingen slutdato. Gyldigheden kan derfor
      ikke afgøres.

    Ingen slutdato må aldrig fortolkes som "stadig gyldig".
    """

    def evaluate(
        self,
        constraint: dict[str, Any],
        *,
        as_of_date: date | None = None,
    ) -> dict[str, Any]:
        evaluation_date = as_of_date or date.today()

        constraint_type = str(
            constraint.get("constraint_type") or ""
        ).strip()

        start_date = self._date_or_none(
            constraint.get("start_date")
        )
        end_date = self._date_or_none(
            constraint.get("end_date")
        )

        if constraint_type == "availability_permit":
            status = self._evaluate_availability_permit(
                start_date=start_date,
                end_date=end_date,
                as_of_date=evaluation_date,
            )
        else:
            status = self._evaluate_generic_constraint(
                start_date=start_date,
                end_date=end_date,
                as_of_date=evaluation_date,
            )

        return {
            "status": status,
            "as_of_date": evaluation_date,
        }

    def _evaluate_availability_permit(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        as_of_date: date,
    ) -> str:
        if (
            start_date is not None
            and start_date > as_of_date
        ):
            return "future"

        if end_date is None:
            return "end_date_unknown"

        if end_date < as_of_date:
            return "expired"

        if end_date == as_of_date:
            return "expires_today"

        return "valid"

    def _evaluate_generic_constraint(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        as_of_date: date,
    ) -> str:
        if (
            start_date is not None
            and start_date > as_of_date
        ):
            return "future"

        if end_date is None:
            return "end_date_unknown"

        if end_date < as_of_date:
            return "expired"

        if end_date == as_of_date:
            return "expires_today"

        return "valid"

    @staticmethod
    def _date_or_none(
        value: date | str | None,
    ) -> date | None:
        if value in (None, ""):
            return None

        if isinstance(value, date):
            return value

        return date.fromisoformat(str(value))
