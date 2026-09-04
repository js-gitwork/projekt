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
    Orkestrerer import af tekniske objekter.

    Servicen har kun ansvar for:

    1. validering
    2. mapping
    3. database-transaktion
    4. udførelse af importplanen

    Den konkrete create/update/upsert-logik ligger i executoren.

    Hele importen er atomisk:
    enten gemmes alle ændringer, eller også gemmes ingen.
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
    ) -> TechnicalAssetImportPlan:
        """
        Validerer og mapper importdata uden at ændre databasen.

        Kan bruges af både preview og egentlig import.
        """
        validation = self.validator.validate(
            import_data
        )

        if not validation.valid:
            raise TechnicalAssetImportValidationError(
                validation.issues
            )

        return self.mapper.map(
            import_data
        )

    def preview(
        self,
        import_data: TechnicalAssetImport,
    ) -> Any:
        """
        Udfører hele importen i en database-transaktion,
        men ruller altid transaktionen tilbage.

        Resultatet kan derfor bruges til at vise, hvad
        importen ville ændre.
        """
        plan = self.prepare(
            import_data
        )

        with SessionLocal() as session:
            try:
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
        """
        Validerer, mapper og gennemfører hele importen
        i én samlet database-transaktion.
        """
        plan = self.prepare(
            import_data
        )

        with SessionLocal() as session:
            try:
                result = self.executor.execute(
                    session,
                    plan,
                )

                if result.has_blocking_conflicts:
                    session.rollback()

                    raise TechnicalAssetImportConflictError(
                        result
                    )

                session.commit()

                return result

            except Exception:
                session.rollback()
                raise