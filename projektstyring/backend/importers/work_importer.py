from __future__ import annotations

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
    Registrerer arbejde på brønde og stik.

    Importerede arbejdsregistreringer skal være idempotente.
    Hvis samme kildepost allerede findes, oprettes den ikke igen.
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

            if self._manhole_work_exists(
                manhole=manhole,
                source_name=plan.source,
                source_reference=(
                    source.source_reference
                ),
                work_type=source.work_type,
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

            repo.record_manhole_work(
                manhole["id"],
                source.work_type,
                status=source.status,
                quantity=source.quantity,
                unit=source.unit,
                performed_date=source.performed_date,
                performed_by=source.performed_by,
                team_id=source.team_id,
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
        connections = repo.list_service_connections(
            project_id=plan.project_id,
        )

        connection_by_external_id = {
            connection["external_id"]: connection
            for connection in connections
        }

        for item in plan.service_connection_work:
            external_id = (
                item.service_connection_key.external_id
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

            if self._service_connection_work_exists(
                connection=connection,
                source_name=plan.source,
                source_reference=(
                    source.source_reference
                ),
                work_type=source.work_type,
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

            repo.record_service_connection_work(
                connection["id"],
                source.work_type,
                status=source.status,
                quantity=source.quantity,
                unit=source.unit,
                performed_date=source.performed_date,
                performed_by=source.performed_by,
                team_id=source.team_id,
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
    def _manhole_work_exists(
        *,
        manhole: dict,
        source_name: str,
        source_reference: str | None,
        work_type: str,
    ) -> bool:
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
                source_reference is not None
                and work.get("source_reference")
                != source_reference
            ):
                continue

            if (
                source_reference is None
                and work.get("work_type")
                != work_type
            ):
                continue

            return True

        return False

    @staticmethod
    def _service_connection_work_exists(
        *,
        connection: dict,
        source_name: str,
        source_reference: str | None,
        work_type: str,
    ) -> bool:
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
                source_reference is not None
                and work.get("source_reference")
                != source_reference
            ):
                continue

            if (
                source_reference is None
                and work.get("work_type")
                != work_type
            ):
                continue

            return True

        return False