from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from projektstyring.backend.importers.technical_asset_import import (
    ImportedManhole,
    ImportedManholeWork,
    ImportedServiceConnection,
    ImportedServiceConnectionWork,
    ImportedStretch,
    TechnicalAssetImport,
)


@dataclass(slots=True, frozen=True)
class ManholeKey:
    project_id: str
    manhole_no: str


@dataclass(slots=True, frozen=True)
class StretchKey:
    project_id: str
    installation_no: str
    bottom_manhole_no: str
    top_manhole_no: str


@dataclass(slots=True, frozen=True)
class ServiceConnectionKey:
    project_id: str
    external_id: str


@dataclass(slots=True)
class MappedManhole:
    key: ManholeKey
    source: ImportedManhole


@dataclass(slots=True)
class MappedStretch:
    key: StretchKey
    sequence: int
    source: ImportedStretch


@dataclass(slots=True)
class MappedServiceConnection:
    key: ServiceConnectionKey
    stretch_key: StretchKey
    source: ImportedServiceConnection


@dataclass(slots=True)
class MappedManholeWork:
    manhole_key: ManholeKey
    source: ImportedManholeWork


@dataclass(slots=True)
class MappedServiceConnectionWork:
    service_connection_key: ServiceConnectionKey
    source: ImportedServiceConnectionWork


@dataclass(slots=True)
class TechnicalAssetImportPlan:
    project_id: str
    source: str

    manholes: list[MappedManhole] = field(
        default_factory=list
    )

    stretches: list[MappedStretch] = field(
        default_factory=list
    )

    service_connections: list[
        MappedServiceConnection
    ] = field(
        default_factory=list
    )

    manhole_work: list[
        MappedManholeWork
    ] = field(
        default_factory=list
    )

    service_connection_work: list[
        MappedServiceConnectionWork
    ] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class TechnicalAssetMapper:
    """
    Omsætter validerede importdata til en kildeuafhængig
    importplan.

    Mapperen skriver aldrig til databasen.

    Alle referencer udtrykkes med stabile forretningsnøgler,
    så importservicen senere kan afgøre, om et objekt skal:

    - oprettes
    - opdateres
    - efterlades uændret
    """

    def map(
        self,
        import_data: TechnicalAssetImport,
    ) -> TechnicalAssetImportPlan:
        project_id = import_data.project_id.strip()
        source = import_data.source.strip()

        plan = TechnicalAssetImportPlan(
            project_id=project_id,
            source=source,
            metadata=dict(import_data.metadata),
        )

        self._map_manholes(
            import_data,
            plan,
        )

        self._map_installations(
            import_data,
            plan,
        )

        self._map_manhole_work(
            import_data,
            plan,
        )

        self._map_service_connection_work(
            import_data,
            plan,
        )

        return plan

    @staticmethod
    def _map_manholes(
        import_data: TechnicalAssetImport,
        plan: TechnicalAssetImportPlan,
    ) -> None:
        for manhole in import_data.manholes:
            plan.manholes.append(
                MappedManhole(
                    key=ManholeKey(
                        project_id=plan.project_id,
                        manhole_no=manhole.manhole_no.strip(),
                    ),
                    source=manhole,
                )
            )

    @staticmethod
    def _map_installations(
        import_data: TechnicalAssetImport,
        plan: TechnicalAssetImportPlan,
    ) -> None:
        for installation in import_data.installations:
            installation_no = (
                installation.installation_no.strip()
            )

            for stretch in installation.stretches:
                stretch_key = StretchKey(
                    project_id=plan.project_id,
                    installation_no=installation_no,
                    bottom_manhole_no=(
                        stretch.bottom_manhole_no.strip()
                    ),
                    top_manhole_no=(
                        stretch.top_manhole_no.strip()
                    ),
                )

                plan.stretches.append(
                    MappedStretch(
                        key=stretch_key,
                        sequence=stretch.sequence,
                        source=stretch,
                    )
                )

                for connection in stretch.service_connections:
                    plan.service_connections.append(
                        MappedServiceConnection(
                            key=ServiceConnectionKey(
                                project_id=plan.project_id,
                                external_id=(
                                    connection.external_id.strip()
                                ),
                            ),
                            stretch_key=stretch_key,
                            source=connection,
                        )
                    )

    @staticmethod
    def _map_manhole_work(
        import_data: TechnicalAssetImport,
        plan: TechnicalAssetImportPlan,
    ) -> None:
        for work in import_data.manhole_work:
            plan.manhole_work.append(
                MappedManholeWork(
                    manhole_key=ManholeKey(
                        project_id=plan.project_id,
                        manhole_no=work.manhole_no.strip(),
                    ),
                    source=work,
                )
            )

    @staticmethod
    def _map_service_connection_work(
        import_data: TechnicalAssetImport,
        plan: TechnicalAssetImportPlan,
    ) -> None:
        for work in import_data.service_connection_work:
            plan.service_connection_work.append(
                MappedServiceConnectionWork(
                    service_connection_key=ServiceConnectionKey(
                        project_id=plan.project_id,
                        external_id=(
                            work
                            .service_connection_external_id
                            .strip()
                        ),
                    ),
                    source=work,
                )
            )
