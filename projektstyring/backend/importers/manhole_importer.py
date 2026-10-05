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
    Opretter og opdaterer fysiske brønde.

    En brønd identificeres ved projekt-id og brøndnummer.
    Den kan indgå i flere stræk uden at få separate dybder.

    Projektoversigten er autoritativ for brønddybder.

    En sekundær brøndoversigt må:
    - oprette en endnu ukendt brønd med en gyldig dybde
    - kontrollere dybden på en eksisterende brønd
    - aldrig overskrive en eksisterende dybde

    Manglende eller modstridende observationer må
    aldrig nulstille en allerede registreret dybde.
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

            # Dybdeoplysninger skal følge den faktiske
            # autoritative måling og ikke blot den
            # senest importerede CSV-fil.
            depth_metadata_fields = {
                "depth_source",
                "depth_authoritative",
                "depth_observations_m",
            }

            if plan.import_type == "manhole_overview":
                # Sekundær import må ikke ændre
                # eksisterende dybdeproveniens.
                for field in depth_metadata_fields:
                    if field in existing_metadata:
                        merged_metadata[field] = (
                            existing_metadata[field]
                        )
                    else:
                        merged_metadata.pop(field, None)

            elif plan.import_type == "project_overview":
                observations = self._depth_observations(item)

                # Kun en entydig positiv observation
                # må erstatte dybdens kildeoplysninger.
                if len(observations) != 1:
                    for field in depth_metadata_fields:
                        if field in existing_metadata:
                            merged_metadata[field] = (
                                existing_metadata[field]
                            )
                        else:
                            merged_metadata.pop(field, None)

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
                        fields=list(updates.keys()),
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
        """
        Håndterer dybdemålinger ud fra importtypens autoritet.

        Projektoversigt:
        - Er autoritativ for brønddybder.
        - En entydig positiv måling må opdatere depth_m.
        - Manglende måling sletter aldrig eksisterende dybde.
        - Modstridende målinger registreres som konflikt.

        Brøndoversigt:
        - Må aldrig ændre depth_m.
        - Kan kontrollere sin måling mod den autoritative dybde.
        """

        observations = self._depth_observations(item)

        existing_raw = existing.get("depth_m")

        existing_depth = (
            Decimal(str(existing_raw))
            if existing_raw is not None
            else None
        )

        # Modstridende målinger i samme import.
        # Den eksisterende dybde bevares altid.
        if len(observations) > 1:
            self._add_depth_conflict(
                result=result,
                manhole_no=item.key.manhole_no,
                existing_value=observations[0],
                incoming_value=observations[1],
                source="c5_internal",
            )
            return

        # Ingen positiv dybdemåling i den nye import.
        # Eksisterende data må ikke nulstilles.
        if not observations:
            return

        incoming_depth = observations[0]

        # Projektoversigten er autoritativ.
        if import_type == "project_overview":
            if existing_depth != incoming_depth:
                updates["depth_m"] = incoming_depth

            return

        # Den sekundære brøndoversigt er ikke autoritativ.
        # Den må kun fungere som kontrol.
        if import_type == "manhole_overview":
            if existing_depth is None:
                return

            difference = abs(
                incoming_depth - existing_depth
            )

            tolerance = Decimal("0.05")

            if difference > tolerance:
                result.conflicts.append(
                    ImportConflict(
                        entity_type="manhole",
                        key=item.key.manhole_no,
                        field="depth_m",
                        existing_value=float(existing_depth),
                        incoming_value=float(incoming_depth),
                        difference=float(difference),
                        tolerance=float(tolerance),
                        message=(
                            f"Brønd {item.key.manhole_no}: "
                            "Dybden i brøndoversigten afviger "
                            "fra projektoversigtens dybde. "
                            f"Projektoversigt: {existing_depth} m. "
                            f"Brøndoversigt: {incoming_depth} m. "
                            "Den autoritative dybde er bevaret."
                        ),
                        blocks_import=False,
                        metadata={
                            "source": "c5_manhole_overview",
                            "requires_review": True,
                        },
                    )
                )

            return

        # Ukendte importtyper må ikke automatisk
        # overskrive den autoritative dybde.
        return

    @staticmethod
    def _depth_observations(
        item: Any,
    ) -> list[Decimal]:
        """
        Returnerer entydige positive dybdemålinger.

        Tomme, ugyldige, negative og nulværdier
        betragtes ikke som registrerede dybder.
        """
        metadata = dict(
            item.source.metadata or {}
        )

        raw_values = metadata.get(
            "depth_observations_m"
        )

        observations: list[Decimal] = []

        def add_value(raw_value: Any) -> None:
            try:
                value = Decimal(str(raw_value))
            except (ValueError, TypeError, ArithmeticError):
                return

            if not value.is_finite() or value <= 0:
                return

            if value not in observations:
                observations.append(value)

        if isinstance(raw_values, list):
            for raw_value in raw_values:
                add_value(raw_value)

        if (
            not observations
            and item.source.depth_m is not None
        ):
            add_value(item.source.depth_m)

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
                    "Ingen af de modstridende målinger "
                    "er anvendt som ny dybde. "
                    "En eventuel eksisterende dybde "
                    "er bevaret. "
                    "Kontroller værdierne i C5."
                ),
                blocks_import=False,
                metadata={
                    "source": source,
                    "requires_review": True,
                },
            )
        )