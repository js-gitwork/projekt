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


class ManholeImporter:
    """
    Opretter eller opdaterer brønde.
    """

    def execute(
        self,
        *,
        repo: TechnicalAssetRepository,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        for item in plan.manholes:
            try:
                existing = repo.get_manhole_by_number(
                    item.key.project_id,
                    item.key.manhole_no,
                )

            except FileNotFoundError:
                repo.create_manhole(
                    item.key.project_id,
                    item.key.manhole_no,
                    diameter_m=item.source.diameter_m,
                    depth_m=item.source.depth_m,
                    profile=item.source.profile,
                    material=item.source.material,
                    active=item.source.active,
                    notes=item.source.notes,
                    metadata=item.source.metadata,
                )

                result.created += 1

                result.actions.append(
                    ImportAction(
                        entity_type="manhole",
                        action="create",
                        key=item.key.manhole_no,
                    )
                )

                continue

            updates: dict[str, Any] = {}

            if (
                existing["diameter_m"]
                != (
                    float(item.source.diameter_m)
                    if item.source.diameter_m is not None
                    else None
                )
            ):
                updates["diameter_m"] = (
                    item.source.diameter_m
                )

            if (
                existing["depth_m"]
                != (
                    float(item.source.depth_m)
                    if item.source.depth_m is not None
                    else None
                )
            ):
                updates["depth_m"] = (
                    item.source.depth_m
                )

            if existing["profile"] != item.source.profile:
                updates["profile"] = (
                    item.source.profile
                )

            if existing["material"] != item.source.material:
                updates["material"] = (
                    item.source.material
                )

            if existing["active"] != item.source.active:
                updates["active"] = (
                    item.source.active
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
                repo.update_manhole(
                    existing["id"],
                    updates,
                )

                result.updated += 1

                result.actions.append(
                    ImportAction(
                        entity_type="manhole",
                        action="update",
                        key=item.key.manhole_no,
                    )
                )

            else:
                result.unchanged += 1

                result.actions.append(
                    ImportAction(
                        entity_type="manhole",
                        action="unchanged",
                        key=item.key.manhole_no,
                    )
                )
