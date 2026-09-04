from __future__ import annotations

from sqlalchemy.orm import Session

from projektstyring.backend.importers.installation_importer import (
    InstallationImporter,
)

from projektstyring.backend.importers.import_result import (
    ImportExecutionResult,
)
from projektstyring.backend.importers.manhole_importer import (
    ManholeImporter,
)
from projektstyring.backend.importers.service_connection_importer import (
    ServiceConnectionImporter,
)
from projektstyring.backend.importers.stretch_importer import (
    StretchImporter,
)
from projektstyring.backend.importers.technical_asset_mapper import (
    TechnicalAssetImportPlan,
)
from projektstyring.backend.importers.work_importer import (
    WorkImporter,
)
from projektstyring.backend.repositories.technical_asset_repository import (
    TechnicalAssetRepository,
)


class TechnicalAssetImportExecutor:
    """
    Udfører en færdig TechnicalAssetImportPlan mod databasen.

    Executoren ejer ikke transaktionen.
    Den bruger den Session, som ImportService giver den.
    """

    def __init__(
        self,
        *,
        manhole_importer: ManholeImporter | None = None,
        stretch_importer: StretchImporter | None = None,
        service_connection_importer:
            ServiceConnectionImporter | None = None,
        work_importer: WorkImporter | None = None,
        installation_importer:
            InstallationImporter | None = None,
    ) -> None:
        self.manhole_importer = (
            manhole_importer
            if manhole_importer is not None
            else ManholeImporter()
        )

        self.stretch_importer = (
            stretch_importer
            if stretch_importer is not None
            else StretchImporter()
        )

        self.service_connection_importer = (
            service_connection_importer
            if service_connection_importer is not None
            else ServiceConnectionImporter()
        )

        self.work_importer = (
            work_importer
            if work_importer is not None
            else WorkImporter()
        )

        self.installation_importer = (
            installation_importer
            if installation_importer is not None
            else InstallationImporter()
        )

    def execute(
        self,
        session: Session,
        plan: TechnicalAssetImportPlan,
    ) -> ImportExecutionResult:
        repo = TechnicalAssetRepository(
            session
        )

        result = ImportExecutionResult(
            project_id=plan.project_id,
            source=plan.source,
        )

        self.installation_importer.execute(
            repo=repo,
            plan=plan,
            result=result,
        )

        self.manhole_importer.execute(
            repo=repo,
            plan=plan,
            result=result,
        )

        self.stretch_importer.execute(
            repo=repo,
            plan=plan,
            result=result,
        )

        self.service_connection_importer.execute(
            repo=repo,
            plan=plan,
            result=result,
        )

        self.work_importer.execute(
            repo=repo,
            plan=plan,
            result=result,
        )

        return result