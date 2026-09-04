from __future__ import annotations

from decimal import Decimal
from typing import Any

from projektstyring.backend.importers.import_result import (
    ImportAction,
    ImportConflict,
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
    Opretter eller beriger brønde.

    Importer er ikke nødvendigvis komplette beskrivelser
    af en brønd. Manglende værdier må derfor ikke nulstille
    eksisterende tekniske oplysninger.

    Brønddybde behandles særligt:

    - eksisterende depth_m betragtes som autoritativ
      grundmåling, typisk fra survey
    - C5-målinger betragtes som observationer
    - forskel <= 5 cm accepteres uden at ændre den
      eksisterende grundmåling
    - forskel > 5 cm opretter en importkonflikt
    - konflikt ændrer aldrig depth_m automatisk
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
                self._create_manhole(
                    repo=repo,
                    item=item,
                    result=result,
                )
                continue

            updates: dict[str, Any] = {}

            self._handle_existing_depth(
                existing=existing,
                item=item,
                import_type=plan.import_type,
                result=result,
                updates=updates,
            )

            if item.source.diameter_m is not None:
                incoming_diameter = float(
                    item.source.diameter_m
                )

                if (
                    existing["diameter_m"]
                    != incoming_diameter
                ):
                    updates["diameter_m"] = (
                        item.source.diameter_m
                    )

            incoming_profile = str(
                item.source.profile or ""
            ).strip()

            if (
                incoming_profile
                and existing["profile"]
                != incoming_profile
            ):
                updates["profile"] = (
                    incoming_profile
                )

            incoming_material = str(
                item.source.material or ""
            ).strip()

            if (
                incoming_material
                and existing["material"]
                != incoming_material
            ):
                updates["material"] = (
                    incoming_material
                )

            incoming_notes = str(
                item.source.notes or ""
            ).strip()

            if (
                incoming_notes
                and existing["notes"]
                != incoming_notes
            ):
                updates["notes"] = (
                    incoming_notes
                )

            existing_metadata = dict(
                existing.get("metadata")
                or {}
            )

            incoming_metadata = dict(
                item.source.metadata
                or {}
            )

            merged_metadata = {
                **existing_metadata,
                **incoming_metadata,
            }

            if (
                merged_metadata
                != existing_metadata
            ):
                updates["metadata"] = (
                    merged_metadata
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

    def _create_manhole(
        self,
        *,
        repo: TechnicalAssetRepository,
        item: Any,
        result: ImportExecutionResult,
    ) -> None:
        observations = self._depth_observations(
            item
        )

        depth_m = None

        if len(observations) > 1:
            self._add_depth_conflict(
                result=result,
                manhole_no=(
                    item.key.manhole_no
                ),
                existing_value=(
                    observations[0]
                ),
                incoming_value=(
                    observations[1]
                ),
                source="c5_internal",
            )

        elif len(observations) == 1:
            depth_m = observations[0]

        repo.create_manhole(
            item.key.project_id,
            item.key.manhole_no,
            diameter_m=item.source.diameter_m,
            depth_m=depth_m,
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

    def _handle_existing_depth(
        self,
        *,
        existing: dict[str, Any],
        item: Any,
        import_type: str,
        result: ImportExecutionResult,
        updates: dict[str, Any],
    ) -> None:
        observations = self._depth_observations(
            item
        )

        existing_raw = existing.get(
            "depth_m"
        )

        #
        # PROJECT OVERVIEW
        #
        # Projektoversigten er autoritativ for brønddybde.
        #
        # Ingen positiv observation:
        #     C5 angiver ingen dybde -> depth_m = None.
        #
        # Én entydig observation:
        #     C5-værdien overskriver databasen.
        #
        # Flere forskellige observationer:
        #     C5 er selvmodsigende.
        #     Ingen dybde gemmes, men resten af importen
        #     må fortsætte.
        #
        if import_type == "project_overview":
            if len(observations) > 1:
                if existing_raw is not None:
                    updates["depth_m"] = None

                self._add_depth_conflict(
                    result=result,
                    manhole_no=(
                        item.key.manhole_no
                    ),
                    existing_value=(
                        observations[0]
                    ),
                    incoming_value=(
                        observations[1]
                    ),
                    source="c5_internal",
                )

                return

            if len(observations) == 1:
                incoming_depth = (
                    observations[0]
                )

                if (
                    existing_raw is None
                    or Decimal(
                        str(existing_raw)
                    )
                    != incoming_depth
                ):
                    updates["depth_m"] = (
                        incoming_depth
                    )

                return

            if existing_raw is not None:
                updates["depth_m"] = None

            return

        #
        # MANHOLE OVERVIEW
        #
        # Brøndoversigten må berige/opdatere en entydig
        # positiv dybde, men manglende/0-værdier må ikke
        # nulstille eksisterende surveydata.
        #
        if len(observations) > 1:
            self._add_depth_conflict(
                result=result,
                manhole_no=(
                    item.key.manhole_no
                ),
                existing_value=(
                    observations[0]
                ),
                incoming_value=(
                    observations[1]
                ),
                source="c5_internal",
            )

            return

        if len(observations) == 1:
            incoming_depth = (
                observations[0]
            )

            if (
                existing_raw is None
                or Decimal(
                    str(existing_raw)
                )
                != incoming_depth
            ):
                updates["depth_m"] = (
                    incoming_depth
                )

        return

    @staticmethod
    def _depth_observations(
        item: Any,
    ) -> list[Decimal]:
        metadata = dict(
            item.source.metadata
            or {}
        )

        raw_values = metadata.get(
            "depth_observations_m"
        )

        observations: list[
            Decimal
        ] = []

        if isinstance(
            raw_values,
            list,
        ):
            for raw_value in raw_values:
                try:
                    value = Decimal(
                        str(raw_value)
                    )
                except Exception:
                    continue

                if value not in observations:
                    observations.append(
                        value
                    )

        if (
            not observations
            and item.source.depth_m
            is not None
        ):
            observations.append(
                Decimal(
                    str(
                        item.source.depth_m
                    )
                )
            )

        return observations

    @staticmethod
    def _add_depth_conflict(
        *,
        result: ImportExecutionResult,
        manhole_no: str,
        existing_value: Decimal,
        incoming_value: Decimal,
        source: str,
    ) -> None:
        difference = abs(
            incoming_value
            - existing_value
        )

        result.conflicts.append(
            ImportConflict(
                entity_type="manhole",
                key=manhole_no,
                field="depth_m",
                existing_value=float(
                    existing_value
                ),
                incoming_value=float(
                    incoming_value
                ),
                difference=float(
                    difference
                ),
                tolerance=0.0,
                message=(
                    f"Brønd {manhole_no} har "
                    "modstridende dybdemål i C5: "
                    f"{existing_value} m og "
                    f"{incoming_value} m. "
                    "Dybden er derfor ikke importeret. "
                    "Ret værdien i C5 og importer igen."
                ),
                blocks_import=False,
                metadata={
                    "source": source,
                    "requires_review": True,
                },
            )
        )