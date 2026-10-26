
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from projektstyring.backend.db_models import Installation, Manhole, Stretch
from projektstyring.backend.importers.import_result import (
    ImportConflict,
    ImportExecutionResult,
)
from projektstyring.backend.importers.technical_asset_mapper import (
    TechnicalAssetImportPlan,
)


class StretchIdentityValidator:
    """
    Kontrollerer uoverensstemmelser mellem C5-importen
    og de eksisterende databasedata.

    Sekvensnummeret bruges til at finde mulige konflikter,
    men er ikke i sig selv bevis for, at et stræk er det samme.
    """

    def validate(
        self,
        *,
        session: Session,
        plan: TechnicalAssetImportPlan,
        result: ImportExecutionResult,
    ) -> None:
        installations = {
            installation.installation_no: installation.id
            for installation in session.scalars(
                select(Installation).where(
                    Installation.project_id == plan.project_id
                )
            )
        }

        manholes = {
            str(manhole.manhole_no).strip(): manhole
            for manhole in session.scalars(
                select(Manhole).where(
                    Manhole.project_id == plan.project_id
                )
            )
        }

        for item in plan.stretches:
            installation_id = installations.get(
                str(item.key.installation_no).strip()
            )

            if installation_id is None:
                continue

            existing = session.scalar(
                select(Stretch).where(
                    Stretch.installation_id == installation_id,
                    Stretch.sequence == item.sequence,
                )
            )

            if existing is None:
                continue

            incoming_bottom = str(
                item.key.bottom_manhole_no
            ).strip()
            incoming_top = str(
                item.key.top_manhole_no
            ).strip()

            existing_bottom = str(existing.from_brond).strip()
            existing_top = str(existing.to_brond).strip()

            if (
                incoming_bottom == existing_bottom
                and incoming_top == existing_top
            ):
                continue

            existing_numbers = (
                f"{existing_bottom} → {existing_top}"
            )
            incoming_numbers = (
                f"{incoming_bottom} → {incoming_top}"
            )

            changed_numbers = {
                incoming_bottom
                if incoming_bottom != existing_bottom
                else None,
                incoming_top
                if incoming_top != existing_top
                else None,
            }
            changed_numbers.discard(None)

            known_manhole_numbers = sorted(
                number
                for number in changed_numbers
                if number in manholes
            )

            message = (
                "Uoverensstemmelse mellem C5-importen og "
                "Rørbots eksisterende database. "
                f"Installation {item.key.installation_no}, "
                f"stræk {item.sequence}. "
                f"Database: {existing_numbers}. "
                f"C5-import: {incoming_numbers}. "
            )

            if known_manhole_numbers:
                message += (
                    "Følgende brøndnumre fra C5 findes allerede "
                    "som fysiske brønde i Rørbots database: "
                    f"{', '.join(known_manhole_numbers)}. "
                )

            message += (
                "Uoverensstemmelsen kan skyldes en tidligere "
                "registreringsfejl, en rettelse i C5 eller "
                "en ændret strækrækkefølge. "
                "Kontrollér, hvilke oplysninger der er korrekte. "
                "Hvis C5 er forkert, kontaktes en C5-superbruger. "
                "Hvis databasen er forkert, skal rettelsen "
                "godkendes og gennemføres uden tab af "
                "eksisterende registreringer. "
                "Importen er blokeret indtil da."
            )

            result.conflicts.append(
                ImportConflict(
                    entity_type="stretch",
                    key=(
                        f"{item.key.installation_no}:"
                        f"{item.sequence}"
                    ),
                    field="manhole_identity",
                    existing_value={
                        "stretch_id": existing.id,
                        "bottom_manhole_no": existing_bottom,
                        "top_manhole_no": existing_top,
                    },
                    incoming_value={
                        "bottom_manhole_no": incoming_bottom,
                        "top_manhole_no": incoming_top,
                    },
                    message=message,
                    blocks_import=True,
                    metadata={
                        "existing_manhole_numbers": (
                            known_manhole_numbers
                        ),
                    },
                )
            )
