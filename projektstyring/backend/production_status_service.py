from __future__ import annotations

from typing import Any

from projektstyring.backend.repositories.technical_asset_repository import (
    TechnicalAssetRepository,
)


def _parse_fraction(
    value: str,
) -> tuple[int, int] | None:
    """
    Parser C5-fraktioner som:

        3/3
        5/1
        2/0
        0/0

    C5-formatet er:

        planlagt / udført

    Funktionen returnerer:

        (udført, planlagt)
    """
    raw = str(value or "").strip()

    if not raw or "/" not in raw:
        return None

    left, right = raw.split("/", 1)

    try:
        planned = int(
            float(left.strip())
        )

        completed = int(
            float(right.strip())
        )

    except (TypeError, ValueError):
        return None

    return completed, planned


def _summarize_fraction_values(
    values: list[str],
) -> dict[str, int]:
    completed = 0
    total = 0

    for value in values:
        parsed = _parse_fraction(value)

        if parsed is None:
            continue

        row_completed, row_total = parsed

        completed += row_completed
        total += row_total

    return {
        "completed": completed,
        "total": total,
        "missing": max(
            0,
            total - completed,
        ),
    }


class ProductionStatusService:
    """
    Bygger en produktionsrestliste direkte fra de tekniske
    objekter i PostgreSQL.

    Servicen ændrer ingen data.
    """

    def __init__(
        self,
        repository: TechnicalAssetRepository | None = None,
    ) -> None:
        self.repository = (
            repository
            if repository is not None
            else TechnicalAssetRepository()
        )

    def build_project_report(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        assets = self.repository.load_project_assets(
            project_id
        )

        installations = []

        project_langhat = {
            "completed": 0,
            "total": 0,
            "missing": 0,
        }

        project_korthat = {
            "completed": 0,
            "total": 0,
            "missing": 0,
        }

        missing_main_stretches = []

        for installation in assets.get(
            "installations",
            [],
        ):
            installation_report = (
                self._build_installation_report(
                    installation
                )
            )

            installations.append(
                installation_report
            )

            langhat = installation_report[
                "langhat"
            ]

            korthat = installation_report[
                "korthat"
            ]

            for key in (
                "completed",
                "total",
                "missing",
            ):
                project_langhat[key] += (
                    langhat[key]
                )

                project_korthat[key] += (
                    korthat[key]
                )

            missing_main_stretches.extend(
                installation_report[
                    "missing_main_stretches"
                ]
            )

        return {
            "project_id": project_id,
            "langhat": project_langhat,
            "korthat": project_korthat,
            "missing_main_stretches": (
                missing_main_stretches
            ),
            "installations": installations,
        }

    def _build_installation_report(
        self,
        installation: dict[str, Any],
    ) -> dict[str, Any]:
        installation_no = str(
            installation.get(
                "installation_no",
                "",
            )
        )

        langhat_values: list[str] = []
        korthat_values: list[str] = []

        missing_main_stretches = []

        for stretch in installation.get(
            "stretches",
            [],
        ):
            metadata = (
                stretch.get("metadata")
                or {}
            )

            c5_values = (
                metadata.get("c5_values")
                or {}
            )

            langhat_values.extend(
                c5_values.get(
                    "langhat",
                    [],
                )
            )

            korthat_values.extend(
                c5_values.get(
                    "korthat",
                    [],
                )
            )

            progress = (
                metadata.get("progress")
                or {}
            )

            hovedledning_progress = (
                progress.get("hovedledning")
            )

            if (
                hovedledning_progress is None
                or hovedledning_progress < 100
            ):
                missing_main_stretches.append(
                    {
                        "installation_no": (
                            installation_no
                        ),
                        "bottom_manhole_no": (
                            stretch.get(
                                "bottom_manhole_no"
                            )
                        ),
                        "top_manhole_no": (
                            stretch.get(
                                "top_manhole_no"
                            )
                        ),
                        "length_m": stretch.get(
                            "length_m"
                        ),
                        "dimension": stretch.get(
                            "dimension"
                        ),
                        "material": stretch.get(
                            "material"
                        ),
                        "progress": (
                            hovedledning_progress
                        ),
                    }
                )

        return {
            "installation_no": installation_no,
            "langhat": (
                _summarize_fraction_values(
                    langhat_values
                )
            ),
            "korthat": (
                _summarize_fraction_values(
                    korthat_values
                )
            ),
            "missing_main_stretches": (
                missing_main_stretches
            ),
        }