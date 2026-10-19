from __future__ import annotations

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


class InstallationImporter:
    """
    Sikrer at installationer fra den tekniske import findes.

    Når importen indeholder expected_stik fra C5,
    opdateres installationens forventede stikantal.

    Importer uden expected_stik ændrer ikke dette felt.
    Øvrige installations- og produktionsdata bevares.
    """

    def execute(
        self,
        *,
        repo: TechnicalAssetRepository,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        installation_numbers: list[str] = []
        expected_stik_by_installation: dict[str, int] = {}

        for stretch in plan.stretches:
            installation_no = str(
                stretch.key.installation_no
            ).strip()

            if not installation_no:
                continue

            if installation_no not in installation_numbers:
                installation_numbers.append(installation_no)

            metadata = stretch.source.metadata or {}

            if "expected_stik" in metadata:
                expected_stik = int(
                    metadata["expected_stik"]
                )

                if expected_stik < 0:
                    raise ValueError(
                        "Negativt stikantal på installation "
                        f"'{installation_no}'."
                    )

                expected_stik_by_installation[
                    installation_no
                ] = (
                    expected_stik_by_installation.get(
                        installation_no,
                        0,
                    )
                    + expected_stik
                )

        for installation_no in installation_numbers:
            created = False

            try:
                repo.get_installation(
                    plan.project_id,
                    installation_no,
                )

            except FileNotFoundError:
                repo.create_installation(
                    plan.project_id,
                    installation_no,
                )

                created = True

                result.created += 1
                result.actions.append(
                    ImportAction(
                        entity_type="installation",
                        action="create",
                        key=installation_no,
                    )
                )

            if installation_no in expected_stik_by_installation:
                expected_stik = expected_stik_by_installation[
                    installation_no
                ]

                repo.update_installation_expected_stik(
                    plan.project_id,
                    installation_no,
                    expected_stik,
                )

                if not created:
                    result.updated += 1
                    result.actions.append(
                        ImportAction(
                            entity_type="installation",
                            action="update",
                            key=installation_no,
                        )
                    )

            elif not created:
                result.unchanged += 1
                result.actions.append(
                    ImportAction(
                        entity_type="installation",
                        action="unchanged",
                        key=installation_no,
                    )
                )