from __future__ import annotations

from sqlalchemy.orm import Session

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.importers.deviation_import import (
    DeviationImport,
)
from projektstyring.backend.importers.import_result import (
    ImportAction,
    ImportConflict,
    ImportExecutionResult,
)
from projektstyring.backend.repositories.deviation_repository import (
    DeviationRepository,
)


class DeviationImportService:
    """
    Importerer C5-afvigelser atomisk.

    Preview udfører samme databaseoperationer som import,
    men ruller transaktionen tilbage.
    """

    def preview(
        self,
        import_data: DeviationImport,
    ) -> ImportExecutionResult:
        with SessionLocal() as session:
            try:
                result = self._execute(
                    session=session,
                    import_data=import_data,
                )

                session.rollback()

                return result

            except Exception:
                session.rollback()
                raise

    def import_deviations(
        self,
        import_data: DeviationImport,
    ) -> ImportExecutionResult:
        with SessionLocal() as session:
            try:
                result = self._execute(
                    session=session,
                    import_data=import_data,
                )

                session.commit()

                return result

            except Exception:
                session.rollback()
                raise

    def _execute(
        self,
        *,
        session: Session,
        import_data: DeviationImport,
    ) -> ImportExecutionResult:
        repo = DeviationRepository(
            session=session
        )

        result = ImportExecutionResult(
            project_id=import_data.project_id,
            source=import_data.source,
        )

        for deviation in import_data.deviations:
            self._add_date_warnings(
                result=result,
                deviation=deviation,
            )

            self._add_invalid_date_warnings(
                result=result,
                deviation=deviation,
            )

            repo_result = repo.upsert_from_c5(
                project_id=import_data.project_id,
                deviation_number=(
                    deviation.deviation_number
                ),
                installation_no=(
                    deviation.installation_no
                ),
                bottom_manhole_no=(
                    deviation.bottom_manhole_no
                ),
                top_manhole_no=(
                    deviation.top_manhole_no
                ),
                dimension_mm=deviation.dimension_mm,
                deviation_type=(
                    deviation.deviation_type
                ),
                description=deviation.description,
                reported_date=(
                    deviation.reported_date
                ),
                completed_date=(
                    deviation.completed_date
                ),
                completed_by=(
                    deviation.completed_by
                ),
                approved_date=(
                    deviation.approved_date
                ),
                source_reference=(
                    deviation.source_reference
                ),
                metadata=deviation.metadata,
            )

            action = repo_result["action"]

            self._add_relation_warnings(
                result=result,
                deviation=deviation,
                stored_deviation=repo_result["deviation"],
            )

            if action == "created":
                result.created += 1

            elif action == "updated":
                result.updated += 1

            elif action == "unchanged":
                result.unchanged += 1

            result.actions.append(
                ImportAction(
                    entity_type="deviation",
                    action=action,
                    key=deviation.deviation_number,
                )
            )

        return result

    @staticmethod
    def _add_relation_warnings(
        *,
        result: ImportExecutionResult,
        deviation,
        stored_deviation: dict,
    ) -> None:
        checks = (
            (
                "installation_no",
                deviation.installation_no,
                stored_deviation.get(
                    "installation_no"
                ),
                "installation",
                "Installation",
            ),
            (
                "bottom_manhole_no",
                deviation.bottom_manhole_no,
                stored_deviation.get(
                    "bottom_manhole_no"
                ),
                "bottom_manhole",
                "Nedstrømsbrønd",
            ),
            (
                "top_manhole_no",
                deviation.top_manhole_no,
                stored_deviation.get(
                    "top_manhole_no"
                ),
                "top_manhole",
                "Opstrømsbrønd",
            ),
        )

        for (
            field_name,
            incoming_value,
            resolved_value,
            warning_type,
            label,
        ) in checks:
            if incoming_value in (
                None,
                "",
            ):
                continue

            if resolved_value not in (
                None,
                "",
            ):
                continue

            result.conflicts.append(
                ImportConflict(
                    entity_type="deviation",
                    key=deviation.deviation_number,
                    field=field_name,
                    existing_value=None,
                    incoming_value=incoming_value,
                    message=(
                        f"{label} "
                        f"'{incoming_value}' "
                        "kunne ikke kobles til "
                        "projektets tekniske data. "
                        "Afvigelsen importeres "
                        "alligevel."
                    ),
                    blocks_import=False,
                    metadata={
                        "warning_type": (
                            f"unresolved_{warning_type}"
                        ),
                    },
                )
            )

    @staticmethod
    def _add_invalid_date_warnings(
        *,
        result: ImportExecutionResult,
        deviation,
    ) -> None:
        metadata = deviation.metadata or {}

        checks = (
            (
                "reported_date",
                "reported_date_raw",
                deviation.reported_date,
                "Oprettet",
            ),
            (
                "completed_date",
                "completed_date_raw",
                deviation.completed_date,
                "Udført dato",
            ),
            (
                "approved_date",
                "approved_date_raw",
                deviation.approved_date,
                "Godkendt",
            ),
        )

        for (
            field_name,
            raw_field_name,
            parsed_value,
            label,
        ) in checks:
            raw_value = str(
                metadata.get(raw_field_name) or ""
            ).strip()

            if not raw_value:
                continue

            if parsed_value is not None:
                continue

            result.conflicts.append(
                ImportConflict(
                    entity_type="deviation",
                    key=deviation.deviation_number,
                    field=field_name,
                    existing_value=None,
                    incoming_value=raw_value,
                    message=(
                        f"{label} '{raw_value}' "
                        "kunne ikke fortolkes som "
                        "en gyldig dato. Den rå "
                        "C5-værdi er bevaret."
                    ),
                    blocks_import=False,
                    metadata={
                        "warning_type": (
                            "invalid_date"
                        ),
                        "raw_field": (
                            raw_field_name
                        ),
                        "raw_value": (
                            raw_value
                        ),
                    },
                )
            )

    @staticmethod
    def _add_date_warnings(
        *,
        result: ImportExecutionResult,
        deviation,
    ) -> None:
        created = deviation.reported_date
        completed = deviation.completed_date
        approved = deviation.approved_date

        if (
            created is not None
            and completed is not None
            and completed < created
        ):
            result.conflicts.append(
                ImportConflict(
                    entity_type="deviation",
                    key=deviation.deviation_number,
                    field="completed_date",
                    existing_value=created,
                    incoming_value=completed,
                    message=(
                        "Udført dato ligger før "
                        "oprettelsesdato."
                    ),
                    blocks_import=False,
                    metadata={
                        "warning_type": (
                            "completed_before_created"
                        ),
                    },
                )
            )

        if (
            completed is not None
            and approved is not None
            and approved < completed
        ):
            result.conflicts.append(
                ImportConflict(
                    entity_type="deviation",
                    key=deviation.deviation_number,
                    field="approved_date",
                    existing_value=completed,
                    incoming_value=approved,
                    message=(
                        "Godkendelsesdato ligger før "
                        "udført dato."
                    ),
                    blocks_import=False,
                    metadata={
                        "warning_type": (
                            "approved_before_completed"
                        ),
                    },
                )
            )
