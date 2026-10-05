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


class StretchImporter:
    """
    Opretter eller opdaterer stræk.
    """

    def execute(
        self,
        *,
        repo: TechnicalAssetRepository,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        for item in plan.stretches:
            try:
                existing = repo.get_stretch_by_manholes(
                    item.key.project_id,
                    item.key.installation_no,
                    item.key.bottom_manhole_no,
                    item.key.top_manhole_no,
                )

            except FileNotFoundError:
                repo.create_stretch(
                    item.key.project_id,
                    item.key.installation_no,
                    sequence=item.sequence,
                    bottom_manhole_no=(
                        item.key.bottom_manhole_no
                    ),
                    top_manhole_no=(
                        item.key.top_manhole_no
                    ),
                    length_m=item.source.length_m,
                    dimension=item.source.dimension,
                    material=item.source.material,
                    stik=len(
                        item.source.service_connections
                    ),
                    notes=item.source.notes,
                    metadata=item.source.metadata,
                )

                result.created += 1

                result.actions.append(
                    ImportAction(
                        entity_type="stretch",
                        action="create",
                        key=(
                            f"{item.key.installation_no}:"
                            f"{item.key.bottom_manhole_no}-"
                            f"{item.key.top_manhole_no}"
                        ),
                    )
                )

                continue

            updates: dict[str, Any] = {}
            changed_metadata_fields: list[str] = []

            if existing["sequence"] != item.sequence:
                updates["sequence"] = item.sequence

            if (
                float(existing["length_m"])
                != float(item.source.length_m)
            ):
                updates["length_m"] = (
                    item.source.length_m
                )

            if (
                existing["dimension"]
                != item.source.dimension
            ):
                updates["dimension"] = (
                    item.source.dimension
                )

            if (
                existing["material"]
                != item.source.material
            ):
                updates["material"] = (
                    item.source.material
                )

            expected_stik = len(
                item.source.service_connections
            )

            if existing["stik"] != expected_stik:
                updates["stik"] = expected_stik

            if existing["notes"] != item.source.notes:
                updates["notes"] = (
                    item.source.notes
                )

            if (
                existing["metadata"]
                != item.source.metadata
            ):
                metadata_fields = sorted(
                    {
                        *existing["metadata"].keys(),
                        *item.source.metadata.keys(),
                    }
                )

                changed_metadata_fields = [
                    key
                    for key in metadata_fields
                    if (
                        existing["metadata"].get(key)
                        != item.source.metadata.get(key)
                    )
                ]

                updates["metadata"] = (
                    item.source.metadata
                )

            if updates:
                repo.update_stretch(
                    existing["id"],
                    **updates,
                )

                result.updated += 1

                existing_values: dict[str, Any] = {}
                incoming_values: dict[str, Any] = {}

                for field in updates.keys():
                    if field == "metadata":
                        for metadata_field in (
                            changed_metadata_fields
                        ):
                            diagnostic_field = (
                                f"metadata:{metadata_field}"
                            )

                            existing_values[
                                diagnostic_field
                            ] = existing["metadata"].get(
                                metadata_field
                            )

                            incoming_values[
                                diagnostic_field
                            ] = item.source.metadata.get(
                                metadata_field
                            )

                    else:
                        existing_values[field] = (
                            existing.get(field)
                        )
                        incoming_values[field] = (
                            updates[field]
                        )

                result.actions.append(
                    ImportAction(
                        entity_type="stretch",
                        action="update",
                        key=(
                            f"{item.key.installation_no}:"
                            f"{item.key.bottom_manhole_no}-"
                            f"{item.key.top_manhole_no}"
                        ),
                        fields=[
                            (
                                "metadata:" + ",".join(
                                    changed_metadata_fields
                                )
                                if field == "metadata"
                                else field
                            )
                            for field in updates.keys()
                        ],
                        existing_values=existing_values,
                        incoming_values=incoming_values,
                    )
                )

            else:
                result.unchanged += 1

                result.actions.append(
                    ImportAction(
                        entity_type="stretch",
                        action="unchanged",
                        key=(
                            f"{item.key.installation_no}:"
                            f"{item.key.bottom_manhole_no}-"
                            f"{item.key.top_manhole_no}"
                        ),
                    )
                )