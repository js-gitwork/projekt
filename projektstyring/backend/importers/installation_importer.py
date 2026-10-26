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
    Opretter manglende installationer og synkroniserer
    stikantal fra importerede strækninger.

    Kun felter, som importen leverer, bliver opdateret.
    """

    def execute(
        self,
        *,
        repo: TechnicalAssetRepository,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        installation_numbers: list[str] = []
        stik_counts: dict[str, dict[str, int]] = {}

        for stretch in plan.stretches:
            installation_no = str(
                stretch.key.installation_no
            ).strip()

            if not installation_no:
                continue

            if installation_no not in installation_numbers:
                installation_numbers.append(installation_no)

            metadata = stretch.source.metadata or {}

            if not any(
                field in metadata
                for field in ("expected_stik", "active_stik")
            ):
                continue

            counts = stik_counts.setdefault(
                installation_no,
                {},
            )

            discontinued = bool(
                metadata.get("c5_discontinued", False)
            )

            for field in ("expected_stik", "active_stik"):
                if field not in metadata:
                    continue

                value = (
                    0
                    if discontinued
                    else int(metadata[field])
                )

                if value < 0:
                    raise ValueError(
                        f"Negativt {field} på installation "
                        f"'{installation_no}'."
                    )

                counts[field] = counts.get(field, 0) + value

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

            counts = stik_counts.get(
                installation_no,
                {},
            )

            if counts:
                changed = repo.update_installation_stik_counts(
                    plan.project_id,
                    installation_no,
                    expected_stik=counts.get("expected_stik"),
                    active_stik=counts.get("active_stik"),
                )

                if changed and not created:
                    result.updated += 1
                    result.actions.append(
                        ImportAction(
                            entity_type="installation",
                            action="update",
                            key=installation_no,
                            fields=list(counts),
                        )
                    )

                elif not changed and not created:
                    result.unchanged += 1
                    result.actions.append(
                        ImportAction(
                            entity_type="installation",
                            action="unchanged",
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