from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import (
    Installation,
    Manhole,
    ManholeWork,
    Project,
    ServiceConnection,
    ServiceConnectionWork,
    Stretch,
)
from projektstyring.backend.importers.technical_asset_import import (
    ImportedInstallationAssets,
    ImportedManhole,
    ImportedServiceConnection,
    ImportedServiceConnectionWork,
    ImportedStretch,
    TechnicalAssetImport,
)
from projektstyring.backend.importers.technical_asset_import_executor import (
    TechnicalAssetImportExecutor,
)
from projektstyring.backend.importers.technical_asset_import_service import (
    TechnicalAssetImportService,
)
from projektstyring.backend.repositories.technical_asset_repository import (
    TechnicalAssetRepository,
)


TEST_PROJECT_ID = "VTEST_ASSET_IMPORT"


def cleanup_test_project() -> None:
    with SessionLocal() as session:
        project = session.get(
            Project,
            TEST_PROJECT_ID,
        )

        if project is None:
            return

        installation_ids = list(
            session.scalars(
                select(Installation.id).where(
                    Installation.project_id
                    == TEST_PROJECT_ID
                )
            )
        )

        stretch_ids: list[int] = []

        if installation_ids:
            stretch_ids = list(
                session.scalars(
                    select(Stretch.id).where(
                        Stretch.installation_id.in_(
                            installation_ids
                        )
                    )
                )
            )

        connection_ids: list[int] = []

        if stretch_ids:
            connection_ids = list(
                session.scalars(
                    select(ServiceConnection.id).where(
                        ServiceConnection.stretch_id.in_(
                            stretch_ids
                        )
                    )
                )
            )

        manhole_ids = list(
            session.scalars(
                select(Manhole.id).where(
                    Manhole.project_id
                    == TEST_PROJECT_ID
                )
            )
        )

        if connection_ids:
            session.execute(
                delete(ServiceConnectionWork).where(
                    ServiceConnectionWork
                    .service_connection_id
                    .in_(connection_ids)
                )
            )

            session.execute(
                delete(ServiceConnection).where(
                    ServiceConnection.id.in_(
                        connection_ids
                    )
                )
            )

        if stretch_ids:
            session.execute(
                delete(Stretch).where(
                    Stretch.id.in_(stretch_ids)
                )
            )

        if manhole_ids:
            session.execute(
                delete(ManholeWork).where(
                    ManholeWork.manhole_id.in_(
                        manhole_ids
                    )
                )
            )

            session.execute(
                delete(Manhole).where(
                    Manhole.id.in_(manhole_ids)
                )
            )

        if installation_ids:
            session.execute(
                delete(Installation).where(
                    Installation.id.in_(
                        installation_ids
                    )
                )
            )

        session.delete(project)
        session.commit()


def create_test_project() -> None:
    with SessionLocal() as session:
        project = Project(
            id=TEST_PROJECT_ID,
            name="Technical Asset Import Test",
            customer="Test",
            city="Test",
            status="upcoming",
            notes="Automatisk integrationstest",
        )

        session.add(project)
        session.flush()

        installation = Installation(
            project_id=TEST_PROJECT_ID,
            installation_no="1",
            sequence=1,
            active=True,
            expected_stik=1,
            active_stik=1,
            opened_stik=0,
            langhatte=0,
            korthatte_extra=0,
            broende=0,
            bronde_total=0,
            hovedledning_meter=18.4,
            notes="",
        )

        session.add(installation)
        session.commit()


def make_import_data() -> TechnicalAssetImport:
    return TechnicalAssetImport(
        project_id=TEST_PROJECT_ID,
        source="integration_test",
        manholes=[
            ImportedManhole(
                manhole_no="4612022",
                diameter_m=Decimal("1.00"),
                depth_m=Decimal("2.50"),
                material="beton",
            ),
            ImportedManhole(
                manhole_no="4612023",
                diameter_m=Decimal("1.00"),
                depth_m=Decimal("2.20"),
                material="beton",
            ),
        ],
        installations=[
            ImportedInstallationAssets(
                installation_no="1",
                stretches=[
                    ImportedStretch(
                        sequence=1,
                        bottom_manhole_no="4612022",
                        top_manhole_no="4612023",
                        length_m=Decimal("18.40"),
                        dimension="500",
                        material="PVC",
                        service_connections=[
                            ImportedServiceConnection(
                                external_id=(
                                    "4612022-"
                                    "4612023-"
                                    "18.40-2"
                                ),
                                bottom_manhole_no=(
                                    "4612022"
                                ),
                                top_manhole_no=(
                                    "4612023"
                                ),
                                position_m=Decimal(
                                    "18.40"
                                ),
                                clock_position="2",
                                sequence=1,
                                dimension_mm=150,
                                material="PVC",
                                active=True,
                                to_be_opened=True,
                            )
                        ],
                    )
                ],
            )
        ],
        service_connection_work=[
            ImportedServiceConnectionWork(
                service_connection_external_id=(
                    "4612022-"
                    "4612023-"
                    "18.40-2"
                ),
                work_type="langhat",
                status="completed",
                quantity=Decimal("1"),
                unit="stk",
                performed_by="Integrationstest",
            )
        ],
    )


def test_technical_asset_import_end_to_end():
    cleanup_test_project()

    try:
        create_test_project()

        service = TechnicalAssetImportService(
            TechnicalAssetImportExecutor()
        )

        result = service.import_assets(
            make_import_data()
        )

        assert result.created == 4
        assert result.updated == 0
        assert result.work_entries_created == 1

        repo = TechnicalAssetRepository()

        assets = repo.load_project_assets(
            TEST_PROJECT_ID
        )

        assert assets["project_id"] == TEST_PROJECT_ID
        assert len(assets["manholes"]) == 2
        assert len(assets["installations"]) == 1

        installation = assets["installations"][0]

        assert installation["installation_no"] == "1"
        assert len(installation["stretches"]) == 1

        stretch = installation["stretches"][0]

        assert (
            stretch["bottom_manhole_no"]
            == "4612022"
        )

        assert (
            stretch["top_manhole_no"]
            == "4612023"
        )

        assert float(stretch["length_m"]) == 18.4
        assert stretch["dimension"] == "500"
        assert stretch["material"] == "PVC"

        assert len(
            stretch["service_connections"]
        ) == 1

        connection = (
            stretch["service_connections"][0]
        )

        assert (
            connection["external_id"]
            == "4612022-4612023-18.40-2"
        )

        assert connection["clock_position"] == "2"
        assert connection["dimension_mm"] == 150
        assert connection["to_be_opened"] is True

        assert len(
            connection["work_entries"]
        ) == 1

        work = connection["work_entries"][0]

        assert work["work_type"] == "langhat"
        assert work["status"] == "completed"
        assert work["source"] == "integration_test"

    finally:
        cleanup_test_project()

def test_technical_asset_import_is_idempotent():
    cleanup_test_project()

    try:
        create_test_project()

        service = TechnicalAssetImportService(
            TechnicalAssetImportExecutor()
        )

        import_data = make_import_data()

        first_result = service.import_assets(
            import_data
        )

        assert first_result.created == 4
        assert first_result.updated == 0
        assert first_result.work_entries_created == 1

        second_result = service.import_assets(
            import_data
        )

        assert second_result.created == 0
        assert second_result.updated == 0
        assert second_result.unchanged == 4

        assert second_result.work_entries_created == 0

        repo = TechnicalAssetRepository()

        assets = repo.load_project_assets(
            TEST_PROJECT_ID
        )

        assert len(assets["manholes"]) == 2
        assert len(assets["installations"]) == 1

        installation = assets["installations"][0]

        assert len(
            installation["stretches"]
        ) == 1

        stretch = installation["stretches"][0]

        assert len(
            stretch["service_connections"]
        ) == 1

        connection = stretch[
            "service_connections"
        ][0]

        assert len(
            connection["work_entries"]
        ) == 1

    finally:
        cleanup_test_project()