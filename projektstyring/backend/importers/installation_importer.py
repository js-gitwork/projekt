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
    Sikrer at installationer fra den tekniske import findes,
    før stræk og øvrige tekniske objekter importeres.

    Installationerne udledes af importplanens stræk.

    Eksisterende installationer ændres ikke.
    Manglende installationer oprettes.
    """

    def execute(
        self,
        *,
        repo: TechnicalAssetRepository,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        installation_numbers = []

        for stretch in plan.stretches:
            installation_no = str(
                stretch.key.installation_no
            ).strip()

            if (
                installation_no
                and installation_no
                not in installation_numbers
            ):
                installation_numbers.append(
                    installation_no
                )

        for installation_no in installation_numbers:
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

                result.created += 1

                result.actions.append(
                    ImportAction(
                        entity_type="installation",
                        action="create",
                        key=installation_no,
                    )
                )

                continue

            result.unchanged += 1

            result.actions.append(
                ImportAction(
                    entity_type="installation",
                    action="unchanged",
                    key=installation_no,
                )
            )
