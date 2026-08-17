from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from projektstyring.backend.importers.import_result import (
    ImportAction,
    ImportExecutionResult,
)
from projektstyring.backend.importers.technical_asset_mapper import (
    TechnicalAssetImportPlan,
)
from projektstyring.backend.repositories.technical_asset_repository import (
    TechnicalAssetRepository,
)


class WorkImporter:
    """
    Registrerer historisk arbejde på brønde og stik.

    Importen er idempotent:

    - samme kildepost og samme tilstand -> unchanged
    - samme kildepost med ændret tilstand -> ny historikpost
    - den nye historikpost superseder den tidligere

    Dermed kan eksempelvis:

        planned

    senere blive til:

        completed

    uden at den tidligere historik går tabt.
    """

    def execute(
        self,
        *,
        repo: TechnicalAssetRepository,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        self._execute_manhole_work(
            repo=repo,
            plan=plan,
            result=result,
        )

        self._execute_service_connection_work(
            repo=repo,
            plan=plan,
            result=result,
        )

    def _execute_manhole_work(
        self,
        *,
        repo: TechnicalAssetRepository,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        manholes = {
            manhole["manhole_no"]: manhole
            for manhole in repo.list_manholes(
                plan.project_id
            )
        }

        for item in plan.manhole_work:
            manhole_no = (
                item.manhole_key.manhole_no
            )

            manhole = manholes.get(
                manhole_no
            )

            if manhole is None:
                raise FileNotFoundError(
                    "Brønd "
                    f"'{manhole_no}' findes ikke "
                    f"på projekt '{plan.project_id}'."
                )

            source = item.source

            previous = (
                self._find_manhole_work(
                    manhole=manhole,
                    source_name=plan.source,
                    source_reference=(
                        source.source_reference
                    ),
                    work_type=source.work_type,
                )
            )

            if (
                previous is not None
                and self._same_work_state(
                    previous,
                    source,
                )
            ):
                result.actions.append(
                    ImportAction(
                        entity_type="manhole_work",
                        action="unchanged",
                        key=(
                            f"{manhole_no}:"
                            f"{source.work_type}"
                        ),
                    )
                )

                continue

            supersedes_work_id = (
                previous.get("id")
                if previous is not None
                else None
            )

            repo.record_manhole_work(
                manhole["id"],
                source.work_type,
                status=source.status,
                quantity=source.quantity,
                unit=source.unit,
                performed_date=source.performed_date,
                performed_by=source.performed_by,
                team_id=source.team_id,
                supersedes_work_id=(
                    supersedes_work_id
                ),
                source=plan.source,
                source_reference=(
                    source.source_reference
                ),
                notes=source.notes,
                metadata=source.metadata,
            )

            result.work_entries_created += 1

            result.actions.append(
                ImportAction(
                    entity_type="manhole_work",
                    action="create",
                    key=(
                        f"{manhole_no}:"
                        f"{source.work_type}"
                    ),
                )
            )

    def _execute_service_connection_work(
        self,
        *,
        repo: TechnicalAssetRepository,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        connections = (
            repo.list_service_connections(
                project_id=plan.project_id,
            )
        )

        connection_by_external_id = {
            connection["external_id"]:
            connection
            for connection in connections
        }

        for item in plan.service_connection_work:
            external_id = (
                item
                .service_connection_key
                .external_id
            )

            connection = (
                connection_by_external_id.get(
                    external_id
                )
            )

            if connection is None:
                raise FileNotFoundError(
                    "Stik "
                    f"'{external_id}' findes ikke "
                    f"på projekt '{plan.project_id}'."
                )

            source = item.source

            previous = (
                self._find_service_connection_work(
                    connection=connection,
                    source_name=plan.source,
                    source_reference=(
                        source.source_reference
                    ),
                    work_type=source.work_type,
                )
            )

            if (
                previous is not None
                and self._same_work_state(
                    previous,
                    source,
                )
            ):
                result.actions.append(
                    ImportAction(
                        entity_type=(
                            "service_connection_work"
                        ),
                        action="unchanged",
                        key=(
                            f"{external_id}:"
                            f"{source.work_type}"
                        ),
                    )
                )

                continue

            supersedes_work_id = (
                previous.get("id")
                if previous is not None
                else None
            )

            repo.record_service_connection_work(
                connection["id"],
                source.work_type,
                status=source.status,
                quantity=source.quantity,
                unit=source.unit,
                performed_date=source.performed_date,
                performed_by=source.performed_by,
                team_id=source.team_id,
                supersedes_work_id=(
                    supersedes_work_id
                ),
                source=plan.source,
                source_reference=(
                    source.source_reference
                ),
                notes=source.notes,
                metadata=source.metadata,
            )

            result.work_entries_created += 1

            result.actions.append(
                ImportAction(
                    entity_type=(
                        "service_connection_work"
                    ),
                    action="create",
                    key=(
                        f"{external_id}:"
                        f"{source.work_type}"
                    ),
                )
            )

    @staticmethod
    def _find_manhole_work(
        *,
        manhole: dict[str, Any],
        source_name: str,
        source_reference: str | None,
        work_type: str,
    ) -> dict[str, Any] | None:
        matches = []

        for work in manhole.get(
            "work_entries",
            [],
        ):
            if (
                work.get("source")
                != source_name
            ):
                continue

            if (
                work.get("work_type")
                != work_type
            ):
                continue

            if source_reference is not None:
                if (
                    work.get("source_reference")
                    != source_reference
                ):
                    continue

            matches.append(work)

        if not matches:
            return None

        return max(
            matches,
            key=lambda work: int(
                work.get("id") or 0
            ),
        )

    @staticmethod
    def _find_service_connection_work(
        *,
        connection: dict[str, Any],
        source_name: str,
        source_reference: str | None,
        work_type: str,
    ) -> dict[str, Any] | None:
        matches = []

        for work in connection.get(
            "work_entries",
            [],
        ):
            if (
                work.get("source")
                != source_name
            ):
                continue

            if (
                work.get("work_type")
                != work_type
            ):
                continue

            if source_reference is not None:
                if (
                    work.get("source_reference")
                    != source_reference
                ):
                    continue

            matches.append(work)

        if not matches:
            return None

        return max(
            matches,
            key=lambda work: int(
                work.get("id") or 0
            ),
        )

    @classmethod
    def _same_work_state(
        cls,
        existing: dict[str, Any],
        source: Any,
    ) -> bool:
        return (
            str(
                existing.get("status")
                or ""
            ).strip()
            == str(
                source.status
                or ""
            ).strip()
            and cls._decimal_value(
                existing.get("quantity")
            )
            == cls._decimal_value(
                source.quantity
            )
            and str(
                existing.get("unit")
                or ""
            ).strip()
            == str(
                source.unit
                or ""
            ).strip()
            and cls._date_value(
                existing.get(
                    "performed_date"
                )
            )
            == cls._date_value(
                source.performed_date
            )
            and cls._optional_text(
                existing.get(
                    "performed_by"
                )
            )
            == cls._optional_text(
                source.performed_by
            )
            and cls._optional_text(
                existing.get("team_id")
            )
            == cls._optional_text(
                source.team_id
            )
            and str(
                existing.get("notes")
                or ""
            ).strip()
            == str(
                source.notes
                or ""
            ).strip()
            and dict(
                existing.get("metadata")
                or {}
            )
            == dict(
                source.metadata
                or {}
            )
        )

    @staticmethod
    def _decimal_value(
        value: Any,
    ) -> Decimal:
        try:
            return Decimal(
                str(value or 0)
            ).normalize()
        except Exception:
            return Decimal("0")

    @staticmethod
    def _date_value(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        if isinstance(value, date):
            return value.isoformat()

        normalized = str(
            value
        ).strip()

        return normalized or None

    @staticmethod
    def _optional_text(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        return normalized or None