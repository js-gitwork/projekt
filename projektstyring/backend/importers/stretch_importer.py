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
    Opretter eller opdaterer stræk og tilhørende opmålingsdata.
    """

    def execute(
        self,
        *,
        repo: TechnicalAssetRepository,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        for item in plan.stretches:
            stretch_key = (
                f"{item.key.installation_no}:"
                f"{item.key.bottom_manhole_no}-"
                f"{item.key.top_manhole_no}"
            )

            try:
                existing = repo.get_stretch_by_manholes(
                    item.key.project_id,
                    item.key.installation_no,
                    item.key.bottom_manhole_no,
                    item.key.top_manhole_no,
                )

            except FileNotFoundError:
                created = repo.create_stretch(
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

                self._save_survey(
                    repo=repo,
                    stretch_id=created["id"],
                    survey=item.source.survey,
                )

                result.created += 1

                result.actions.append(
                    ImportAction(
                        entity_type="stretch",
                        action="create",
                        key=stretch_key,
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
                        key=stretch_key,
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
                        key=stretch_key,
                    )
                )

            self._save_survey(
                repo=repo,
                stretch_id=existing["id"],
                survey=item.source.survey,
            )

    @staticmethod
    def _save_survey(
        *,
        repo: TechnicalAssetRepository,
        stretch_id: int,
        survey: Any,
    ) -> None:
        """
        Gemmer opmålingen, hvis importkilden indeholder en.

        survey=None betyder, at importen ikke er en
        opmålingsimport. Eksisterende opmålingsdata røres
        derfor ikke.
        """
        if survey is None:
            return

        repo.upsert_stretch_survey(
            stretch_id,
            existing_profile=survey.existing_profile,
            existing_dimension=survey.existing_dimension,
            existing_material=survey.existing_material,
            existing_length_m=survey.existing_length_m,
            planned_dimension=survey.planned_dimension,
            planned_length_m=survey.planned_length_m,
            traffic=survey.traffic,
            bottom_cannot_open=(
                survey.bottom_cannot_open
            ),
            bottom_profile=survey.bottom_profile,
            bottom_dimension_a_mm=(
                survey.bottom_dimension_a_mm
            ),
            bottom_dimension_b_mm=(
                survey.bottom_dimension_b_mm
            ),
            bottom_material=survey.bottom_material,
            top_cannot_open=(
                survey.top_cannot_open
            ),
            top_profile=survey.top_profile,
            top_dimension_a_mm=(
                survey.top_dimension_a_mm
            ),
            top_dimension_b_mm=(
                survey.top_dimension_b_mm
            ),
            top_material=survey.top_material,
            measured_by=survey.measured_by,
            notes=survey.notes,
            raw_data=survey.raw_data,
        )