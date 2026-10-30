
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from projektstyring.backend.c5_sync.reader import (
    MAINLINE_TYPES,
    clean,
    connect,
    read_service_work,
    read_stretches,
)


def _has_valid_date(value: Any) -> bool:
    if isinstance(value, (datetime, date)):
        return value.year > 1900
    return False


def _positive_quantity(value: Any) -> bool:
    if value is None:
        return False

    try:
        return Decimal(
            str(value).strip().replace(",", ".")
        ) > 0
    except (InvalidOperation, ValueError):
        return False


def _summary(
    planned: int,
    completed: int,
) -> dict[str, int]:
    return {
        "total": planned,
        "completed": completed,
        "missing": max(0, planned - completed),
    }


def _installation_number(value: Any) -> str:
    return clean(value).replace(",", ".")


class ProductionStatusService:
    """
    Læser aktuel produktion direkte fra C5 SQL Server.

    Ingen import og ingen lokal kopi af C5-data.

    Brøndstræk knyttes til installationer gennem POSITIONTXT.

    Stikarbejder opgøres på projektniveau, indtil
    REFID-relationen er verificeret. Der gættes ikke på
    installationsfordelingen.
    """

    def build_project_report(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        connection = connect()

        try:
            stretches = read_stretches(
                connection,
                project_id,
            )
            service_work = read_service_work(
                connection,
                project_id,
            )
        finally:
            connection.close()

        return self._build_report(
            project_id=project_id,
            stretches=stretches,
            service_work=service_work,
        )

    def _build_report(
        self,
        *,
        project_id: str,
        stretches: list[dict[str, Any]],
        service_work: list[dict[str, Any]],
    ) -> dict[str, Any]:
        installation_rows: dict[
            str, list[dict[str, Any]]
        ] = {}

        all_mainline = []

        for stretch in stretches:
            if stretch.get("INSTEJER") not in MAINLINE_TYPES:
                continue

            all_mainline.append(stretch)

            number = _installation_number(
                stretch.get("POSITIONTXT")
            )

            if number:
                installation_rows.setdefault(
                    number, []
                ).append(stretch)

        installations = []
        missing_main_stretches = []

        for number, rows in sorted(
            installation_rows.items()
        ):
            missing = []

            for row in rows:
                if _has_valid_date(
                    row.get("INSTALLATIONDATO")
                ):
                    continue

                stretch = {
                    "installation_no": number,
                    "bottom_manhole_no": clean(
                        row.get("BRXND1")
                    ),
                    "top_manhole_no": clean(
                        row.get("BRXND2")
                    ),
                    "length_m": (
                        row.get("NYLEDTVLXNGDE")
                    ),
                    "dimension": (
                        row.get("NYLEDDIM")
                    ),
                    "material": None,
                    "progress": None,
                }

                missing.append(stretch)

            missing_main_stretches.extend(missing)

            mainline_completed = sum(
                _has_valid_date(
                    row.get("INSTALLATIONDATO")
                )
                for row in rows
            )

            preparation_completed = sum(
                self._approved(
                    row.get("TVKONTROLGODKENDT")
                )
                for row in rows
            )

            installations.append({
                "installation_no": number,
                "forarbejde": _summary(
                    len(rows),
                    preparation_completed,
                ),
                "hovedledning": _summary(
                    len(rows),
                    mainline_completed,
                ),
                "langhat": _summary(0, 0),
                "korthat": _summary(0, 0),
                "broendskud": _summary(0, 0),
                "pkt_rep": _summary(0, 0),
                "missing_main_stretches": missing,
            })

        # Disse tal er pr. projekt.
        # REFID -> installation er endnu ikke verificeret.
        work_fields = {
            "langhat": "STIKLH",
            "korthat": "STIKKH",
            "broendskud": "STIKBRXND",
        }

        work_summaries = {}

        for work_type, field in work_fields.items():
            relevant = [
                row
                for row in service_work
                if _positive_quantity(row.get(field))
            ]

            completed = sum(
                _has_valid_date(
                    row.get("FXRDIGDATO")
                )
                for row in relevant
            )

            work_summaries[work_type] = _summary(
                len(relevant),
                completed,
            )

        mainline = _summary(
            len(all_mainline),
            sum(
                _has_valid_date(
                    row.get("INSTALLATIONDATO")
                )
                for row in all_mainline
            ),
        )

        preparation = _summary(
            len(all_mainline),
            sum(
                self._approved(
                    row.get("TVKONTROLGODKENDT")
                )
                for row in all_mainline
            ),
        )

        return {
            "project_id": project_id,
            "source": "c5_sql_live",
            "forarbejde": preparation,
            "hovedledning": mainline,
            "langhat": work_summaries["langhat"],
            "korthat": work_summaries["korthat"],
            "broendskud": work_summaries["broendskud"],
            "pkt_rep": _summary(0, 0),
            "missing_main_stretches": (
                missing_main_stretches
            ),
            "installations": installations,
            "service_work_installation_mapping_known": False,
        }

    @staticmethod
    def _approved(value: Any) -> bool:
        if value is None:
            return False

        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float, Decimal)):
            return value != 0

        return str(value).strip().casefold() in {
            "1",
            "ja",
            "yes",
            "true",
            "godkendt",
        }
