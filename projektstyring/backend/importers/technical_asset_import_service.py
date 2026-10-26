from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.importers.technical_asset_import import (
    TechnicalAssetImport,
)
from projektstyring.backend.importers.technical_asset_mapper import (
    TechnicalAssetImportPlan,
    TechnicalAssetMapper,
)
from projektstyring.backend.importers.technical_asset_validator import (
    TechnicalAssetValidator,
    ValidationIssue,
)


class TechnicalAssetImportExecutor(Protocol):
    """
    Interface for den komponent, som udfører en valideret
    og mappet importplan mod databasen.
    """

    def execute(
        self,
        session: Session,
        plan: TechnicalAssetImportPlan,
    ) -> Any:
        ...


class TechnicalAssetImportValidationError(ValueError):
    """
    Rejses når importerede data ikke består valideringen.
    """

    def __init__(
        self,
        issues: list[ValidationIssue],
    ) -> None:
        self.issues = issues

        messages = [
            f"{issue.path}: {issue.message}"
            for issue in issues
            if issue.severity == "error"
        ]

        super().__init__(
            "; ".join(messages)
            or "Importdata er ugyldige."
        )
class TechnicalAssetImportConflictError(
    ValueError
):
    """
    Rejses når preview/import finder forhold,
    som kræver menneskelig stillingtagen.
    """

    def __init__(
        self,
        result: Any,
    ) -> None:
        self.result = result

        super().__init__(
            "Importen indeholder uafklarede "
            "konflikter og er ikke gemt."
        )

class TechnicalAssetImportService:
    """
    Validerer, mapper og importerer tekniske C5-data.

    Eksisterende brønde på projektet indgår i
    referencevalideringen.

    Preview rulles altid tilbage.
    Import gennemføres atomisk.
    """

    def __init__(
        self,
        executor: TechnicalAssetImportExecutor,
        *,
        validator: TechnicalAssetValidator | None = None,
        mapper: TechnicalAssetMapper | None = None,
    ) -> None:
        self.executor = executor

        self.validator = (
            validator
            if validator is not None
            else TechnicalAssetValidator()
        )

        self.mapper = (
            mapper
            if mapper is not None
            else TechnicalAssetMapper()
        )

    def prepare(
        self,
        import_data: TechnicalAssetImport,
        session: Session | None = None,
    ) -> TechnicalAssetImportPlan:
        validation = self.validator.validate(
            import_data,
            session=session,
        )

        if not validation.valid:
            raise TechnicalAssetImportValidationError(
                validation.issues
            )

        return self.mapper.map(import_data)

    def preview(
        self,
        import_data: TechnicalAssetImport,
    ) -> Any:
        with SessionLocal() as session:
            try:
                plan = self.prepare(
                    import_data,
                    session=session,
                )

                result = self.executor.execute(
                    session,
                    plan,
                )

                session.rollback()
                return result

            except Exception:
                session.rollback()
                raise

    def import_assets(
        self,
        import_data: TechnicalAssetImport,
    ) -> Any:
        with SessionLocal() as session:
            try:
                plan = self.prepare(
                    import_data,
                    session=session,
                )

                result = self.executor.execute(
                    session,
                    plan,
                )

                if result.has_blocking_conflicts:
                    raise TechnicalAssetImportConflictError(
                        result
                    )

                session.commit()
                return result

            except Exception:
                session.rollback()
                raise