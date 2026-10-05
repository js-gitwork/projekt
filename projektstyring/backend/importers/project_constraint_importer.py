from __future__ import annotations

from typing import Any

from projektstyring.backend.importers.import_result import (
    ImportAction,
    ImportConflict,
    ImportExecutionResult,
)
from projektstyring.backend.importers.technical_asset_mapper import (
    TechnicalAssetImportPlan,
)
from projektstyring.backend.repositories.project_constraint_repository import (
    ProjectConstraintRepository,
)


class ProjectConstraintImporter:
    """
    Importerer projektmæssige constraints.

    Constraints er faktadata for Rørbot/watchdog og er ikke
    en del af den normale planlægningsmotor.

    Vigtig kildebeskyttelse:
    - C5 må oprette og opdatere C5-ejede constraints.
    - C5 må ikke tavst overskrive en constraint, som er
      registreret fra en anden kilde, fx projektleder/Rørbot.
    - Ved uenighed bevares den eksisterende værdi, og der
      oprettes en ikke-blokerende importkonflikt.
    """

    def execute(
        self,
        *,
        repo: ProjectConstraintRepository,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        self._add_import_metadata_warnings(
            plan=plan,
            result=result,
        )

        for mapped_constraint in plan.project_constraints:
            constraint = mapped_constraint.source

            constraint_type = str(
                constraint.constraint_type or ""
            ).strip()

            reference = str(
                constraint.reference or ""
            ).strip()

            source = str(
                constraint.source or plan.source or ""
            ).strip()

            key = self._build_key(
                constraint_type=constraint_type,
                reference=reference,
            )

            self._add_constraint_warnings(
                result=result,
                key=key,
                constraint=constraint,
            )

            existing = self._find_existing(
                repo=repo,
                project_id=plan.project_id,
                constraint_type=constraint_type,
                reference=reference,
            )

            if (
                existing is not None
                and source == "c5"
                and existing.get("source") != "c5"
            ):
                differences = self._find_differences(
                    existing=existing,
                    incoming={
                        "start_date": constraint.start_date,
                        "end_date": constraint.end_date,
                        "notes": str(
                            constraint.notes or ""
                        ).strip(),
                        "metadata": dict(
                            constraint.metadata or {}
                        ),
                    },
                )

                if differences:
                    self._add_source_conflicts(
                        result=result,
                        key=key,
                        existing=existing,
                        incoming=constraint,
                        differences=differences,
                    )

                self._register_action(
                    result=result,
                    action="unchanged",
                    key=key,
                )

                continue

            upsert_result = repo.upsert(
                project_id=plan.project_id,
                constraint_type=constraint_type,
                reference=reference,
                start_date=constraint.start_date,
                end_date=constraint.end_date,
                source=source,
                source_reference=(
                    constraint.source_reference
                ),
                notes=constraint.notes,
                metadata=constraint.metadata,
            )

            action = str(
                upsert_result["action"]
            ).strip()

            self._register_action(
                result=result,
                action=action,
                key=key,
            )

    @staticmethod
    def _add_import_metadata_warnings(
        *,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        """
        Tilføjer advarsler for C5-observationer, som ikke kan
        omsættes sikkert til egentlige constraints.
        """

        metadata = plan.metadata

        if not isinstance(metadata, dict):
            return

        observations = metadata.get(
            "missing_permit_references"
        )

        if not isinstance(observations, list):
            return

        for index, observation in enumerate(
            observations,
            start=1,
        ):
            if not isinstance(observation, dict):
                continue

            installation_no = str(
                observation.get(
                    "installation_no"
                )
                or ""
            ).strip()

            permit_week = str(
                observation.get(
                    "permit_week"
                )
                or ""
            ).strip()

            start_date_raw = str(
                observation.get(
                    "start_date_raw"
                )
                or ""
            ).strip()

            end_date_raw = str(
                observation.get(
                    "end_date_raw"
                )
                or ""
            ).strip()

            location_text = (
                f" på installation {installation_no}"
                if installation_no
                else ""
            )

            result.conflicts.append(
                ImportConflict(
                    entity_type="project_constraint",
                    key=(
                        "availability_permit:"
                        f"missing_reference:{index}"
                    ),
                    field="reference",
                    existing_value=None,
                    incoming_value=None,
                    message=(
                        "C5 indeholder oplysninger om en "
                        f"rådighedstilladelse{location_text}, "
                        "men Tilladnr. mangler. "
                        "Rækken er ikke oprettet som "
                        "projektconstraint."
                    ),
                    blocks_import=False,
                    metadata={
                        "warning_type": (
                            "missing_permit_reference"
                        ),
                        "source": "c5",
                        "installation_no": (
                            installation_no
                        ),
                        "permit_week": permit_week,
                        "start_date_raw": (
                            start_date_raw
                        ),
                        "end_date_raw": (
                            end_date_raw
                        ),
                    },
                )
            )

    @staticmethod
    def _add_constraint_warnings(
        *,
        result: ImportExecutionResult,
        key: str,
        constraint: Any,
    ) -> None:
        """
        Tilføjer ikke-blokerende advarsler for usikre eller
        modstridende constraint-data fra kildesystemet.

        Rå kildeværdier bevares i metadata.
        Der foretages ingen automatisk rettelse.
        """

        if str(
            constraint.constraint_type or ""
        ).strip() != "availability_permit":
            return

        metadata = constraint.metadata

        if not isinstance(metadata, dict):
            return

        start_date_raw = str(
            metadata.get("start_date_raw") or ""
        ).strip()

        end_date_raw = str(
            metadata.get("end_date_raw") or ""
        ).strip()

        if (
            start_date_raw
            and constraint.start_date is None
            and not metadata.get(
                "conflicting_start_dates"
            )
        ):
            result.conflicts.append(
                ImportConflict(
                    entity_type="project_constraint",
                    key=key,
                    field="start_date",
                    existing_value=None,
                    incoming_value=start_date_raw,
                    message=(
                        "Tillad-start "
                        f"'{start_date_raw}' kunne ikke "
                        "fortolkes som en gyldig dato. "
                        "Den rå C5-værdi er bevaret."
                    ),
                    blocks_import=False,
                    metadata={
                        "warning_type": "invalid_date",
                        "source": "c5",
                        "raw_field": "Tillad-start",
                        "raw_value": start_date_raw,
                    },
                )
            )

        if (
            end_date_raw
            and constraint.end_date is None
            and not metadata.get(
                "conflicting_end_dates"
            )
        ):
            result.conflicts.append(
                ImportConflict(
                    entity_type="project_constraint",
                    key=key,
                    field="end_date",
                    existing_value=None,
                    incoming_value=end_date_raw,
                    message=(
                        "Tillad-slut "
                        f"'{end_date_raw}' kunne ikke "
                        "fortolkes som en gyldig dato. "
                        "Den rå C5-værdi er bevaret."
                    ),
                    blocks_import=False,
                    metadata={
                        "warning_type": "invalid_date",
                        "source": "c5",
                        "raw_field": "Tillad-slut",
                        "raw_value": end_date_raw,
                    },
                )
            )

        conflict_fields = (
            (
                "conflicting_start_dates",
                "start_date",
                "Tillad-start",
                "start_date_raw_values",
            ),
            (
                "conflicting_end_dates",
                "end_date",
                "Tillad-slut",
                "end_date_raw_values",
            ),
            (
                "conflicting_permit_weeks",
                "permit_week",
                "Tillad-uge",
                "permit_week_values",
            ),
        )

        for (
            flag_name,
            field_name,
            c5_field_name,
            values_name,
        ) in conflict_fields:
            if not metadata.get(flag_name):
                continue

            raw_values = metadata.get(
                values_name
            )

            if not isinstance(raw_values, list):
                raw_values = []

            result.conflicts.append(
                ImportConflict(
                    entity_type="project_constraint",
                    key=key,
                    field=field_name,
                    existing_value=None,
                    incoming_value=raw_values,
                    message=(
                        f"Samme rådighedstilladelse "
                        f"indeholder flere forskellige "
                        f"værdier i {c5_field_name}: "
                        f"{raw_values}. "
                        "Der er ikke valgt en værdi "
                        "automatisk."
                    ),
                    blocks_import=False,
                    metadata={
                        "warning_type": (
                            "conflicting_constraint_values"
                        ),
                        "source": "c5",
                        "raw_field": c5_field_name,                    "raw_values": raw_values,
                },
            )
        )

    @staticmethod
    def _find_existing(
        *,
        repo: ProjectConstraintRepository,
        project_id: str,
        constraint_type: str,
        reference: str,
    ) -> dict[str, Any] | None:
        constraints = repo.list_by_type(
            project_id,
            constraint_type,
        )

        for constraint in constraints:
            if (
                str(
                    constraint.get("reference") or ""
                ).strip()
                == reference
            ):
                return constraint

        return None

    @staticmethod
    def _find_differences(
        *,
        existing: dict[str, Any],
        incoming: dict[str, Any],
    ) -> list[str]:
        differences: list[str] = []

        for field_name in (
            "start_date",
            "end_date",
            "notes",
            "metadata",
        ):
            if (
                existing.get(field_name)
                != incoming.get(field_name)
            ):
                differences.append(
                    field_name
                )

        return differences

    @staticmethod
    def _add_source_conflicts(
        *,
        result: ImportExecutionResult,
        key: str,
        existing: dict[str, Any],
        incoming: Any,
        differences: list[str],
    ) -> None:
        incoming_values = {
            "start_date": incoming.start_date,
            "end_date": incoming.end_date,
            "notes": str(
                incoming.notes or ""
            ).strip(),
            "metadata": dict(
                incoming.metadata or {}
            ),
        }

        for field_name in differences:
            result.conflicts.append(
                ImportConflict(
                    entity_type="project_constraint",
                    key=key,
                    field=field_name,
                    existing_value=existing.get(
                        field_name
                    ),
                    incoming_value=incoming_values.get(
                        field_name
                    ),
                    message=(
                        "C5-værdien afviger fra en "
                        "projektconstraint registreret fra "
                        f"kilden '{existing.get('source')}'. "
                        "Den eksisterende værdi er bevaret."
                    ),
                    blocks_import=False,
                    metadata={
                        "warning_type": (
                            "constraint_source_conflict"
                        ),
                        "existing_source": (
                            existing.get("source")
                        ),
                        "incoming_source": "c5",
                    },
                )
            )

    @staticmethod
    def _build_key(
        *,
        constraint_type: str,
        reference: str,
    ) -> str:
        if reference:
            return (
                f"{constraint_type}:"
                f"{reference}"
            )

        return constraint_type

    @staticmethod
    def _register_action(
        *,
        result: ImportExecutionResult,
        action: str,
        key: str,
    ) -> None:
        normalized_action = str(
            action
        ).strip()

        if normalized_action == "created":
            result.created += 1
            action_name = "create"

        elif normalized_action == "updated":
            result.updated += 1
            action_name = "update"

        else:
            result.unchanged += 1
            action_name = "unchanged"

        result.actions.append(
            ImportAction(
                entity_type="project_constraint",
                action=action_name,
                key=key,
            )
        )
