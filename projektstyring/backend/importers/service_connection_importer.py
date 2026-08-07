from __future__ import annotations

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


class ServiceConnectionImporter:
    """
    Opretter eller opdaterer stik.
    """

    def execute(
        self,
        *,
        repo: TechnicalAssetRepository,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        for item in plan.service_connections:
            stretch = repo.get_stretch_by_manholes(
                item.stretch_key.project_id,
                item.stretch_key.installation_no,
                item.stretch_key.bottom_manhole_no,
                item.stretch_key.top_manhole_no,
            )

            stretch_id = stretch["id"]

            existing = self._find_existing(
                repo=repo,
                project_id=item.key.project_id,
                external_id=item.key.external_id,
            )

            if existing is None:
                repo.create_service_connection(
                    stretch_id,
                    item.key.external_id,
                    position_m=item.source.position_m,
                    clock_position=(
                        item.source.clock_position
                    ),
                    sequence=item.source.sequence,
                    dimension_mm=(
                        item.source.dimension_mm
                    ),
                    material=item.source.material,
                    active=item.source.active,
                    to_be_opened=(
                        item.source.to_be_opened
                    ),
                    decommissioned=(
                        item.source.decommissioned
                    ),
                    notes=item.source.notes,
                    metadata=item.source.metadata,
                )

                result.created += 1

                result.actions.append(
                    ImportAction(
                        entity_type="service_connection",
                        action="create",
                        key=item.key.external_id,
                    )
                )

                continue

            if existing["stretch_id"] != stretch_id:
                raise ValueError(
                    "Stikket "
                    f"'{item.key.external_id}' findes allerede "
                    "på et andet stræk. Hvis placeringen er "
                    "ændret, skal stikket have en ny "
                    "DANDAS-identitet."
                )

            updates: dict[str, Any] = {}

            if (
                existing["sequence"]
                != item.source.sequence
            ):
                updates["sequence"] = (
                    item.source.sequence
                )

            if (
                existing["dimension_mm"]
                != item.source.dimension_mm
            ):
                updates["dimension_mm"] = (
                    item.source.dimension_mm
                )

            if (
                existing["material"]
                != item.source.material
            ):
                updates["material"] = (
                    item.source.material
                )

            if (
                existing["active"]
                != item.source.active
            ):
                updates["active"] = (
                    item.source.active
                )

            if (
                existing["to_be_opened"]
                != item.source.to_be_opened
            ):
                updates["to_be_opened"] = (
                    item.source.to_be_opened
                )

            if (
                existing["decommissioned"]
                != item.source.decommissioned
            ):
                updates["decommissioned"] = (
                    item.source.decommissioned
                )

            if existing["notes"] != item.source.notes:
                updates["notes"] = (
                    item.source.notes
                )

            if (
                existing["metadata"]
                != item.source.metadata
            ):
                updates["metadata"] = (
                    item.source.metadata
                )

            if updates:
                repo.update_service_connection(
                    existing["id"],
                    updates,
                )

                result.updated += 1

                result.actions.append(
                    ImportAction(
                        entity_type="service_connection",
                        action="update",
                        key=item.key.external_id,
                    )
                )

            else:
                result.unchanged += 1

                result.actions.append(
                    ImportAction(
                        entity_type="service_connection",
                        action="unchanged",
                        key=item.key.external_id,
                    )
                )

    @staticmethod
    def _find_existing(
        *,
        repo: TechnicalAssetRepository,
        project_id: str,
        external_id: str,
    ) -> dict[str, Any] | None:
        connections = repo.list_service_connections(
            project_id=project_id,
        )

        for connection in connections:
            if connection["external_id"] == external_id:
                return connection

        return None
