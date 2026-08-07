from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from projektstyring.backend.importers.technical_asset_import import (
    ImportedInstallationAssets,
    ImportedManhole,
    ImportedServiceConnection,
    ImportedStretch,
    TechnicalAssetImport,
)


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    path: str
    severity: str = "error"


@dataclass(slots=True)
class ValidationResult:
    issues: list[ValidationIssue] = field(
        default_factory=list
    )

    @property
    def valid(self) -> bool:
        return not any(
            issue.severity == "error"
            for issue in self.issues
        )

    def add_error(
        self,
        code: str,
        message: str,
        path: str,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                code=code,
                message=message,
                path=path,
                severity="error",
            )
        )

    def add_warning(
        self,
        code: str,
        message: str,
        path: str,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                code=code,
                message=message,
                path=path,
                severity="warning",
            )
        )


class TechnicalAssetValidator:
    def validate(
        self,
        import_data: TechnicalAssetImport,
    ) -> ValidationResult:
        result = ValidationResult()

        self._validate_header(
            import_data,
            result,
        )

        self._validate_manholes(
            import_data.manholes,
            result,
        )

        self._validate_installations(
            import_data.installations,
            result,
        )

        self._validate_cross_references(
            import_data,
            result,
        )

        return result

    @staticmethod
    def _validate_header(
        import_data: TechnicalAssetImport,
        result: ValidationResult,
    ) -> None:
        if not import_data.project_id.strip():
            result.add_error(
                "missing_project_id",
                "Projekt-id mangler.",
                "project_id",
            )

        if not import_data.source.strip():
            result.add_error(
                "missing_source",
                "Datakilde mangler.",
                "source",
            )

    @staticmethod
    def _validate_manholes(
        manholes: Iterable[ImportedManhole],
        result: ValidationResult,
    ) -> None:
        seen: set[str] = set()

        for index, manhole in enumerate(manholes):
            path = f"manholes[{index}]"

            manhole_no = manhole.manhole_no.strip()

            if not manhole_no:
                result.add_error(
                    "missing_manhole_no",
                    "Brøndnummer mangler.",
                    path,
                )
                continue

            if manhole_no in seen:
                result.add_error(
                    "duplicate_manhole",
                    (
                        "Brøndnummer "
                        f"'{manhole_no}' forekommer flere gange."
                    ),
                    path,
                )

            seen.add(manhole_no)

            if (
                manhole.diameter_m is not None
                and manhole.diameter_m < 0
            ):
                result.add_error(
                    "invalid_manhole_diameter",
                    "Brønddiameter må ikke være negativ.",
                    path,
                )

            if (
                manhole.depth_m is not None
                and manhole.depth_m < 0
            ):
                result.add_error(
                    "invalid_manhole_depth",
                    "Brønddybde må ikke være negativ.",
                    path,
                )

    def _validate_installations(
        self,
        installations: Iterable[
            ImportedInstallationAssets
        ],
        result: ValidationResult,
    ) -> None:
        seen_installations: set[str] = set()

        for installation_index, installation in enumerate(
            installations
        ):
            path = (
                f"installations[{installation_index}]"
            )

            installation_no = (
                installation.installation_no.strip()
            )

            if not installation_no:
                result.add_error(
                    "missing_installation_no",
                    "Installationsnummer mangler.",
                    path,
                )

            if installation_no in seen_installations:
                result.add_error(
                    "duplicate_installation",
                    (
                        "Installation "
                        f"'{installation_no}' forekommer flere gange."
                    ),
                    path,
                )

            seen_installations.add(installation_no)

            self._validate_stretches(
                installation,
                installation_index,
                result,
            )

    def _validate_stretches(
        self,
        installation: ImportedInstallationAssets,
        installation_index: int,
        result: ValidationResult,
    ) -> None:
        seen_sequences: set[int] = set()
        seen_stretches: set[tuple[str, str]] = set()

        for stretch_index, stretch in enumerate(
            installation.stretches
        ):
            path = (
                f"installations[{installation_index}]"
                f".stretches[{stretch_index}]"
            )

            if stretch.sequence in seen_sequences:
                result.add_error(
                    "duplicate_stretch_sequence",
                    (
                        "Stræk-sekvens "
                        f"{stretch.sequence} forekommer flere gange "
                        "i samme installation."
                    ),
                    path,
                )

            seen_sequences.add(stretch.sequence)

            bottom = stretch.bottom_manhole_no.strip()
            top = stretch.top_manhole_no.strip()

            if not bottom:
                result.add_error(
                    "missing_bottom_manhole",
                    "Bundbrønd mangler.",
                    path,
                )

            if not top:
                result.add_error(
                    "missing_top_manhole",
                    "Topbrønd mangler.",
                    path,
                )

            if bottom and top and bottom == top:
                result.add_error(
                    "same_bottom_and_top_manhole",
                    (
                        "Bundbrønd og topbrønd må ikke være "
                        "den samme."
                    ),
                    path,
                )

            stretch_identity = (
                bottom,
                top,
            )

            if stretch_identity in seen_stretches:
                result.add_error(
                    "duplicate_stretch",
                    (
                        "Strækket "
                        f"'{bottom}-{top}' forekommer flere gange "
                        "i samme installation."
                    ),
                    path,
                )

            seen_stretches.add(stretch_identity)

            if stretch.length_m < 0:
                result.add_error(
                    "invalid_stretch_length",
                    "Stræklængde må ikke være negativ.",
                    path,
                )

            self._validate_service_connections(
                stretch,
                path,
                result,
            )

    @staticmethod
    def _validate_service_connections(
        stretch: ImportedStretch,
        stretch_path: str,
        result: ValidationResult,
    ) -> None:
        seen_external_ids: set[str] = set()
        seen_positions: set[
            tuple[Decimal, str]
        ] = set()

        for connection_index, connection in enumerate(
            stretch.service_connections
        ):
            path = (
                f"{stretch_path}"
                f".service_connections[{connection_index}]"
            )

            external_id = (
                connection.external_id.strip()
            )

            if not external_id:
                result.add_error(
                    "missing_service_connection_id",
                    "Stikidentitet mangler.",
                    path,
                )

            if external_id in seen_external_ids:
                result.add_error(
                    "duplicate_service_connection",
                    (
                        "Stikidentiteten "
                        f"'{external_id}' forekommer flere gange "
                        "på samme stræk."
                    ),
                    path,
                )

            seen_external_ids.add(external_id)

            if connection.position_m < 0:
                result.add_error(
                    "invalid_service_connection_position",
                    "Stikkets position må ikke være negativ.",
                    path,
                )

            if not connection.clock_position.strip():
                result.add_error(
                    "missing_clock_position",
                    "Stikkets urretning mangler.",
                    path,
                )

            position_identity = (
                connection.position_m,
                connection.clock_position.strip(),
            )

            if position_identity in seen_positions:
                result.add_error(
                    "duplicate_service_connection_position",
                    (
                        "Der findes flere stik på samme position "
                        "og urretning."
                    ),
                    path,
                )

            seen_positions.add(position_identity)

            if (
                connection.dimension_mm is not None
                and connection.dimension_mm <= 0
            ):
                result.add_error(
                    "invalid_service_connection_dimension",
                    "Stikdimension skal være større end 0.",
                    path,
                )

            if (
                connection.bottom_manhole_no.strip()
                != stretch.bottom_manhole_no.strip()
                or connection.top_manhole_no.strip()
                != stretch.top_manhole_no.strip()
            ):
                result.add_error(
                    "service_connection_stretch_mismatch",
                    (
                        "Stikkets bund- og topbrønd matcher "
                        "ikke det stræk, som stikket ligger på."
                    ),
                    path,
                )

    @staticmethod
    def _validate_cross_references(
        import_data: TechnicalAssetImport,
        result: ValidationResult,
    ) -> None:
        manhole_numbers = {
            manhole.manhole_no.strip()
            for manhole in import_data.manholes
            if manhole.manhole_no.strip()
        }

        service_connection_ids: set[str] = set()

        for installation in import_data.installations:
            for stretch in installation.stretches:
                for manhole_no in (
                    stretch.bottom_manhole_no.strip(),
                    stretch.top_manhole_no.strip(),
                ):
                    if (
                        manhole_no
                        and manhole_no not in manhole_numbers
                    ):
                        result.add_error(
                            "unknown_manhole",
                            (
                                "Strækket refererer til ukendt "
                                f"brønd '{manhole_no}'."
                            ),
                            (
                                "installations"
                                f"[{installation.installation_no}]"
                            ),
                        )

                for connection in (
                    stretch.service_connections
                ):
                    service_connection_ids.add(
                        connection.external_id.strip()
                    )

        for index, work in enumerate(
            import_data.manhole_work
        ):
            if (
                work.manhole_no.strip()
                not in manhole_numbers
            ):
                result.add_error(
                    "unknown_manhole_for_work",
                    (
                        "Brøndarbejde refererer til ukendt "
                        f"brønd '{work.manhole_no}'."
                    ),
                    f"manhole_work[{index}]",
                )

        for index, work in enumerate(
            import_data.service_connection_work
        ):
            if (
                work.service_connection_external_id.strip()
                not in service_connection_ids
            ):
                result.add_error(
                    "unknown_service_connection_for_work",
                    (
                        "Stikarbejde refererer til ukendt stik "
                        f"'{work.service_connection_external_id}'."
                    ),
                    f"service_connection_work[{index}]",
                )
