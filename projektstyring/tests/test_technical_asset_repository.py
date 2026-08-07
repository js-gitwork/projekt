from __future__ import annotations

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
from projektstyring.backend.repositories.technical_asset_repository import (
    TechnicalAssetRepository,
)


TEST_PROJECT_ID = "VTEST_TECHNICAL_ASSETS"


def cleanup_test_project() -> None:
    """
    Fjerner alle data oprettet af denne integrationstest.

    Vi sletter eksplicit i korrekt rækkefølge, fordi de tekniske
    objekter bevidst bruger RESTRICT flere steder for at beskytte
    historiske produktionsdata.
    """
    with SessionLocal() as session:
        project = session.get(Project, TEST_PROJECT_ID)

        if project is None:
            return

        installation_ids = list(
            session.scalars(
                select(Installation.id).where(
                    Installation.project_id == TEST_PROJECT_ID
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

        service_connection_ids: list[int] = []

        if stretch_ids:
            service_connection_ids = list(
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
                    Manhole.project_id == TEST_PROJECT_ID
                )
            )
        )

        if service_connection_ids:
            session.execute(
                delete(ServiceConnectionWork).where(
                    ServiceConnectionWork.service_connection_id.in_(
                        service_connection_ids
                    )
                )
            )

            session.execute(
                delete(ServiceConnection).where(
                    ServiceConnection.id.in_(
                        service_connection_ids
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


def create_test_structure() -> int:
    """
    Opretter projekt, installation og ét eksisterende stræk.

    De nye tekniske objekter oprettes derefter gennem repository-laget.
    """
    with SessionLocal() as session:
        project = Project(
            id=TEST_PROJECT_ID,
            name="Technical asset integration test",
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
        session.flush()

        stretch = Stretch(
            installation_id=installation.id,
            sequence=1,
            from_brond="4612022",
            to_brond="4612023",
            length_m=18.4,
            dimension="500",
            material="PVC",
            stik=1,
            notes="",
            metadata_data={},
        )

        session.add(stretch)
        session.commit()

        return stretch.id


def test_technical_asset_repository_end_to_end():
    cleanup_test_project()

    try:
        stretch_id = create_test_structure()

        repo = TechnicalAssetRepository()

        bottom = repo.create_manhole(
            TEST_PROJECT_ID,
            "4612022",
            diameter_m=1.0,
            depth_m=2.5,
            material="beton",
        )

        top = repo.create_manhole(
            TEST_PROJECT_ID,
            "4612023",
            diameter_m=1.0,
            depth_m=2.2,
            material="beton",
        )

        linked_stretch = repo.link_stretch_manholes(
            stretch_id,
            bottom_manhole_id=bottom["id"],
            top_manhole_id=top["id"],
        )

        assert (
            linked_stretch["bottom_manhole_no"]
            == "4612022"
        )
        assert (
            linked_stretch["top_manhole_no"]
            == "4612023"
        )

        connection = repo.create_service_connection(
            stretch_id,
            "4612022-4612023-18.40-2",
            position_m=18.40,
            clock_position="2",
            sequence=1,
            dimension_mm=150,
            material="PVC",
            active=True,
            to_be_opened=True,
        )

        assert (
            connection["external_id"]
            == "4612022-4612023-18.40-2"
        )

        work = repo.record_service_connection_work(
            connection["id"],
            "langhat",
            status="completed",
            quantity=1,
            performed_by="Integrationstest",
            source="test",
        )

        assert work["work_type"] == "langhat"
        assert work["status"] == "completed"

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

        assert stretch["bottom_manhole_no"] == "4612022"
        assert stretch["top_manhole_no"] == "4612023"
        assert len(stretch["service_connections"]) == 1

        loaded_connection = (
            stretch["service_connections"][0]
        )

        assert (
            loaded_connection["external_id"]
            == "4612022-4612023-18.40-2"
        )

        assert len(
            loaded_connection["work_entries"]
        ) == 1

        loaded_work = (
            loaded_connection["work_entries"][0]
        )

        assert loaded_work["work_type"] == "langhat"
        assert loaded_work["status"] == "completed"

    finally:
        cleanup_test_project()
