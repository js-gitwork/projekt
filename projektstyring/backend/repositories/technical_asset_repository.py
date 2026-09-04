from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

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


def decimal_or_none(
    value: Decimal | float | int | str | None,
) -> Decimal | None:
    if value in (None, ""):
        return None

    return Decimal(str(value))


def date_or_none(
    value: date | str | None,
) -> date | None:
    if value in (None, ""):
        return None

    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value))


class TechnicalAssetRepository:
    """
    Databaseadgang til projektets tekniske objekter:

    - brønde
    - stræk
    - stik
    - arbejde på brønde
    - arbejde på stik

    Repository-metoderne returnerer almindelige dictionaries,
    så SQLAlchemy-objekter ikke bruges efter sessionen er lukket.
    """

    def __init__(
        self,
        session: Session | None = None,
    ) -> None:
        self._session = session

    def _owns_session(self) -> bool:
        return self._session is None

    def _save_changes(
        self,
        session: Session,
    ) -> None:
        if self._owns_session():
            session.commit()
            return

        session.flush()

    def _rollback(
        self,
        session: Session,
    ) -> None:
        if self._owns_session():
            session.rollback()

    @contextmanager
    def _session_scope(self):
        """
        Returnerer enten den eksterne session eller opretter en
        midlertidig intern session.

        Hvis repository'et har fået en session udefra, er det den
        kaldende kode der ejer commit()/rollback().

        Ellers fungerer repository'et som hidtil.
        """

        if self._session is not None:
            yield self._session
            return

        with SessionLocal() as session:
            yield session

    def load_project_assets(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        """
        Henter projektets komplette tekniske objektstruktur.
        """
        with self._session_scope() as session:
            project_statement = (
                select(Project)
                .where(Project.id == project_id)
                .options(
                    selectinload(Project.manholes).selectinload(
                        Manhole.work_entries
                    ),
                    selectinload(Project.installations)
                    .selectinload(Installation.stretches)
                    .selectinload(Stretch.bottom_manhole),
                    selectinload(Project.installations)
                    .selectinload(Installation.stretches)
                    .selectinload(Stretch.top_manhole),
                    selectinload(Project.installations)
                    .selectinload(Installation.stretches)
                    .selectinload(Stretch.service_connections)
                    .selectinload(
                        ServiceConnection.work_entries
                    ),
                )
            )

            project = session.scalar(project_statement)

            if project is None:
                raise FileNotFoundError(
                    f"Projektet '{project_id}' findes ikke."
                )

            return self._project_assets_to_dict(project)

    def list_manholes(
        self,
        project_id: str,
    ) -> list[dict[str, Any]]:
        """
        Henter alle brønde i et projekt.
        """
        with self._session_scope() as session:
            self._require_project(session, project_id)

            statement = (
                select(Manhole)
                .where(Manhole.project_id == project_id)
                .options(
                    selectinload(Manhole.work_entries),
                )
                .order_by(
                    Manhole.manhole_no.asc(),
                )
            )

            manholes = session.scalars(statement).all()

            return [
                self._manhole_to_dict(manhole)
                for manhole in manholes
            ]

    def get_manhole(
        self,
        manhole_id: int,
    ) -> dict[str, Any]:
        """
        Henter én brønd ud fra databasens interne id.
        """
        with self._session_scope() as session:
            statement = (
                select(Manhole)
                .where(Manhole.id == manhole_id)
                .options(
                    selectinload(Manhole.work_entries),
                )
            )

            manhole = session.scalar(statement)

            if manhole is None:
                raise FileNotFoundError(
                    f"Brønd med id {manhole_id} findes ikke."
                )

            return self._manhole_to_dict(manhole)

    def get_manhole_by_number(
        self,
        project_id: str,
        manhole_no: str,
    ) -> dict[str, Any]:
        """
        Henter en brønd ud fra projekt og brøndnummer.
        """
        normalized_manhole_no = str(manhole_no).strip()

        with self._session_scope() as session:
            statement = (
                select(Manhole)
                .where(
                    Manhole.project_id == project_id,
                    Manhole.manhole_no
                    == normalized_manhole_no,
                )
                .options(
                    selectinload(Manhole.work_entries),
                )
            )

            manhole = session.scalar(statement)

            if manhole is None:
                raise FileNotFoundError(
                    "Brønden "
                    f"'{normalized_manhole_no}' findes ikke "
                    f"på projekt '{project_id}'."
                )

            return self._manhole_to_dict(manhole)

    def create_manhole(
        self,
        project_id: str,
        manhole_no: str,
        *,
        diameter_m: Decimal | float | int | str | None = None,
        depth_m: Decimal | float | int | str | None = None,
        profile: str = "",
        material: str = "",
        active: bool = True,
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Opretter en fysisk brønd.

        Kombinationen project_id + manhole_no er unik.
        """
        normalized_manhole_no = str(manhole_no).strip()

        if not normalized_manhole_no:
            raise ValueError("Brøndnummer må ikke være tomt.")

        with self._session_scope() as session:
            self._require_project(session, project_id)

            manhole = Manhole(
                project_id=project_id,
                manhole_no=normalized_manhole_no,
                diameter_m=decimal_or_none(diameter_m),
                depth_m=decimal_or_none(depth_m),
                profile=str(profile or "").strip(),
                material=str(material or "").strip(),
                active=bool(active),
                notes=str(notes or "").strip(),
                metadata_data=dict(metadata or {}),
            )

            session.add(manhole)

            try:
                self._save_changes(session)
                session.refresh(manhole)
            except IntegrityError as exc:
                self._rollback(session)
                raise ValueError(
                    "Brøndnummeret "
                    f"'{normalized_manhole_no}' findes allerede "
                    f"på projekt '{project_id}'."
                ) from exc
            except Exception:
                self._rollback(session)
                raise

            return self._manhole_to_dict(manhole)

    def update_manhole(
        self,
        manhole_id: int,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Opdaterer tilladte tekniske oplysninger på en brønd.

        Historiske arbejdsregistreringer ændres ikke her.
        """
        allowed_fields = {
            "manhole_no",
            "diameter_m",
            "depth_m",
            "profile",
            "material",
            "active",
            "notes",
            "metadata",
        }

        with self._session_scope() as session:
            manhole = session.get(Manhole, manhole_id)

            if manhole is None:
                raise FileNotFoundError(
                    f"Brønd med id {manhole_id} findes ikke."
                )

            for key, value in updates.items():
                if key not in allowed_fields:
                    continue

                if key == "manhole_no":
                    normalized_value = str(value or "").strip()

                    if not normalized_value:
                        raise ValueError(
                            "Brøndnummer må ikke være tomt."
                        )

                    manhole.manhole_no = normalized_value
                    continue

                if key in {"diameter_m", "depth_m"}:
                    setattr(
                        manhole,
                        key,
                        decimal_or_none(value),
                    )
                    continue

                if key == "active":
                    manhole.active = bool(value)
                    continue

                if key == "metadata":
                    manhole.metadata_data = dict(value or {})
                    continue

                setattr(
                    manhole,
                    key,
                    str(value or "").strip(),
                )

            try:
                self._save_changes(session)
                session.refresh(manhole)
            except IntegrityError as exc:
                self._rollback(session)
                raise ValueError(
                    "Brøndnummeret findes allerede "
                    "på dette projekt."
                ) from exc
            except Exception:
                self._rollback(session)
                raise

            return self._manhole_to_dict(manhole)

    def get_installation(
        self,
        project_id: str,
        installation_no: str,
    ) -> dict[str, Any]:
        normalized_installation_no = str(
            installation_no
        ).strip()

        with self._session_scope() as session:
            installation = session.scalar(
                select(Installation).where(
                    Installation.project_id
                    == project_id,
                    Installation.installation_no
                    == normalized_installation_no,
                )
            )

            if installation is None:
                raise FileNotFoundError(
                    "Installation "
                    f"'{normalized_installation_no}' findes ikke "
                    f"på projekt '{project_id}'."
                )

            return {
                "id": installation.id,
                "project_id": installation.project_id,
                "installation_no": (
                    installation.installation_no
                ),
                "sequence": installation.sequence,
                "active": installation.active,
            }

    def create_installation(
        self,
        project_id: str,
        installation_no: str,
    ) -> dict[str, Any]:
        normalized_installation_no = str(
            installation_no
        ).strip()

        if not normalized_installation_no:
            raise ValueError(
                "Installationsnummer skal angives."
            )

        with self._session_scope() as session:
            project = session.get(
                Project,
                project_id,
            )

            if project is None:
                raise FileNotFoundError(
                    f"Projekt '{project_id}' findes ikke."
                )

            existing = session.scalar(
                select(Installation).where(
                    Installation.project_id
                    == project_id,
                    Installation.installation_no
                    == normalized_installation_no,
                )
            )

            if existing is not None:
                return {
                    "id": existing.id,
                    "project_id": existing.project_id,
                    "installation_no": (
                        existing.installation_no
                    ),
                    "sequence": existing.sequence,
                    "active": existing.active,
                }

            existing_sequences = list(
                session.scalars(
                    select(
                        Installation.sequence
                    ).where(
                        Installation.project_id
                        == project_id
                    )
                )
            )

            next_sequence = (
                max(existing_sequences) + 1
                if existing_sequences
                else 1
            )

            installation = Installation(
                project_id=project_id,
                installation_no=(
                    normalized_installation_no
                ),
                sequence=next_sequence,
                active=True,
                expected_stik=0,
                active_stik=0,
                opened_stik=0,
                langhatte=0,
                korthatte_extra=0,
                broende=0,
                bronde_total=0,
                hovedledning_meter=0.0,
                notes="",
            )

            session.add(
                installation
            )

            try:
                self._save_changes(
                    session
                )

            except IntegrityError as exc:
                self._rollback(
                    session
                )

                raise ValueError(
                    "Installationen kunne ikke oprettes: "
                    f"{project_id}/"
                    f"{normalized_installation_no}."
                ) from exc

            return {
                "id": installation.id,
                "project_id": installation.project_id,
                "installation_no": (
                    installation.installation_no
                ),
                "sequence": installation.sequence,
                "active": installation.active,
            }

    def get_stretch_by_manholes(
        self,
        project_id: str,
        installation_no: str,
        bottom_manhole_no: str,
        top_manhole_no: str,
    ) -> dict[str, Any]:
        """
        Henter et stræk ud fra dets stabile forretningsidentitet:

        projekt
        + installation
        + bundbrønd
        + topbrønd

        De eksisterende from_brond/to_brond-felter bruges også
        under overgangsperioden, så ældre importerede stræk kan
        findes, før de normaliserede Manhole-relationer er sat.
        """
        normalized_installation_no = str(
            installation_no
        ).strip()
        normalized_bottom = str(
            bottom_manhole_no
        ).strip()
        normalized_top = str(
            top_manhole_no
        ).strip()

        with self._session_scope() as session:
            installation = session.scalar(
                select(Installation).where(
                    Installation.project_id == project_id,
                    Installation.installation_no
                    == normalized_installation_no,
                )
            )

            if installation is None:
                raise FileNotFoundError(
                    "Installation "
                    f"'{normalized_installation_no}' findes ikke "
                    f"på projekt '{project_id}'."
                )

            statement = (
                select(Stretch)
                .where(
                    Stretch.installation_id
                    == installation.id,
                    Stretch.from_brond
                    == normalized_bottom,
                    Stretch.to_brond
                    == normalized_top,
                )
                .options(
                    selectinload(Stretch.bottom_manhole),
                    selectinload(Stretch.top_manhole),
                    selectinload(
                        Stretch.service_connections
                    ).selectinload(
                        ServiceConnection.work_entries
                    ),
                )
            )

            stretch = session.scalar(statement)

            if stretch is None:
                raise FileNotFoundError(
                    "Strækket "
                    f"'{normalized_bottom}-{normalized_top}' "
                    "findes ikke på installation "
                    f"'{normalized_installation_no}' "
                    f"i projekt '{project_id}'."
                )

            return self._stretch_to_dict(stretch)

    def create_stretch(
        self,
        project_id: str,
        installation_no: str,
        *,
        sequence: int,
        bottom_manhole_no: str,
        top_manhole_no: str,
        length_m: Decimal | float | int | str,
        dimension: str = "",
        material: str = "",
        stik: int = 0,
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_installation_no = str(
            installation_no
        ).strip()
        normalized_bottom = str(
            bottom_manhole_no
        ).strip()
        normalized_top = str(
            top_manhole_no
        ).strip()

        normalized_length = decimal_or_none(
            length_m
        )

        if normalized_length is None:
            raise ValueError(
                "Stræklængde skal angives."
            )

        if normalized_bottom == normalized_top:
            raise ValueError(
                "Bundbrønd og topbrønd må ikke være den samme."
            )

        with self._session_scope() as session:
            installation = session.scalar(
                select(Installation).where(
                    Installation.project_id == project_id,
                    Installation.installation_no
                    == normalized_installation_no,
                )
            )

            if installation is None:
                raise FileNotFoundError(
                    "Installation "
                    f"'{normalized_installation_no}' findes ikke "
                    f"på projekt '{project_id}'."
                )

            bottom_manhole = session.scalar(
                select(Manhole).where(
                    Manhole.project_id == project_id,
                    Manhole.manhole_no == normalized_bottom,
                )
            )

            top_manhole = session.scalar(
                select(Manhole).where(
                    Manhole.project_id == project_id,
                    Manhole.manhole_no == normalized_top,
                )
            )

            if bottom_manhole is None:
                raise FileNotFoundError(
                    f"Bundbrønd '{normalized_bottom}' findes ikke."
                )

            if top_manhole is None:
                raise FileNotFoundError(
                    f"Topbrønd '{normalized_top}' findes ikke."
                )

            stretch = Stretch(
                installation_id=installation.id,
                bottom_manhole_id=bottom_manhole.id,
                top_manhole_id=top_manhole.id,
                sequence=int(sequence),
                from_brond=normalized_bottom,
                to_brond=normalized_top,
                length_m=float(normalized_length),
                dimension=str(dimension or "").strip(),
                material=str(material or "").strip(),
                stik=int(stik),
                notes=str(notes or "").strip(),
                metadata_data=dict(metadata or {}),
            )

            session.add(stretch)

            try:
                if self._session is None:
                    session.commit()
                else:
                    session.flush()

                session.refresh(stretch)

            except IntegrityError as exc:
                if self._session is None:
                    session.rollback()

                raise ValueError(
                    "Strækket kunne ikke oprettes. "
                    "Kontrollér sekvens og eksisterende stræk."
                ) from exc

            except Exception:
                if self._session is None:
                    session.rollback()
                raise

            return self._stretch_to_dict(stretch)

    def update_stretch(
        self,
        stretch_id: int,
        *,
        sequence: int | None = None,
        length_m: Decimal | float | int | str | None = None,
        dimension: str | None = None,
        material: str | None = None,
        stik: int | None = None,
        notes: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        with self._session_scope() as session:

            stretch = session.get(
                Stretch,
                stretch_id,
            )

            if stretch is None:
                raise FileNotFoundError(
                    f"Stræk {stretch_id} findes ikke."
                )

            if sequence is not None:
                stretch.sequence = int(sequence)

            if length_m is not None:
                value = decimal_or_none(length_m)

                if value is None:
                    raise ValueError(
                        "Ugyldig længde."
                    )

                stretch.length_m = float(value)

            if dimension is not None:
                stretch.dimension = (
                    str(dimension).strip()
                )

            if material is not None:
                stretch.material = (
                    str(material).strip()
                )

            if stik is not None:
                stretch.stik = int(stik)

            if notes is not None:
                stretch.notes = str(notes)

            if metadata is not None:
                stretch.metadata_data = dict(
                    metadata
                )

            try:
                if self._session is None:
                    session.commit()
                else:
                    session.flush()

                session.refresh(stretch)

            except Exception:

                if self._session is None:
                    session.rollback()

                raise

            return self._stretch_to_dict(
                stretch
            )

    def link_stretch_manholes(
        self,
        stretch_id: int,
        *,
        bottom_manhole_id: int,
        top_manhole_id: int,
    ) -> dict[str, Any]:
        """
        Knytter et stræk til dets bund- og topbrønd.

        Begge brønde skal høre til samme projekt som strækket.
        """
        if bottom_manhole_id == top_manhole_id:
            raise ValueError(
                "Bundbrønd og topbrønd må ikke være den samme."
            )

        with self._session_scope() as session:
            stretch = session.get(Stretch, stretch_id)

            if stretch is None:
                raise FileNotFoundError(
                    f"Stræk med id {stretch_id} findes ikke."
                )

            installation = session.get(
                Installation,
                stretch.installation_id,
            )

            if installation is None:
                raise RuntimeError(
                    "Strækkets installation findes ikke."
                )

            bottom_manhole = session.get(
                Manhole,
                bottom_manhole_id,
            )
            top_manhole = session.get(
                Manhole,
                top_manhole_id,
            )

            if bottom_manhole is None:
                raise FileNotFoundError(
                    "Bundbrønd med id "
                    f"{bottom_manhole_id} findes ikke."
                )

            if top_manhole is None:
                raise FileNotFoundError(
                    "Topbrønd med id "
                    f"{top_manhole_id} findes ikke."
                )

            for manhole in (
                bottom_manhole,
                top_manhole,
            ):
                if manhole.project_id != installation.project_id:
                    raise ValueError(
                        "Brønd og stræk skal høre til "
                        "samme projekt."
                    )

            stretch.bottom_manhole_id = bottom_manhole.id
            stretch.top_manhole_id = top_manhole.id

            # De eksisterende tekstfelter holdes midlertidigt
            # synkroniserede af hensyn til kompatibilitet.
            stretch.from_brond = bottom_manhole.manhole_no
            stretch.to_brond = top_manhole.manhole_no

            try:
                self._save_changes(session)
                session.refresh(stretch)
            except Exception:
                self._rollback(session)
                raise

            return self._stretch_to_dict(stretch)

    def list_service_connections(
        self,
        *,
        project_id: str | None = None,
        stretch_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Henter stik for enten et projekt eller et bestemt stræk.
        """
        if project_id is None and stretch_id is None:
            raise ValueError(
                "Angiv enten project_id eller stretch_id."
            )

        with self._session_scope() as session:
            statement = (
                select(ServiceConnection)
                .join(
                    Stretch,
                    ServiceConnection.stretch_id == Stretch.id,
                )
                .join(
                    Installation,
                    Stretch.installation_id == Installation.id,
                )
                .options(
                    selectinload(
                        ServiceConnection.work_entries
                    ),
                )
            )

            if stretch_id is not None:
                statement = statement.where(
                    ServiceConnection.stretch_id == stretch_id
                )

            if project_id is not None:
                statement = statement.where(
                    Installation.project_id == project_id
                )

            statement = statement.order_by(
                ServiceConnection.stretch_id.asc(),
                ServiceConnection.sequence.asc(),
                ServiceConnection.position_m.asc(),
            )

            connections = session.scalars(statement).all()

            return [
                self._service_connection_to_dict(connection)
                for connection in connections
            ]

    def get_service_connection(
        self,
        service_connection_id: int,
    ) -> dict[str, Any]:
        """
        Henter ét fysisk stik.
        """
        with self._session_scope() as session:
            statement = (
                select(ServiceConnection)
                .where(
                    ServiceConnection.id
                    == service_connection_id
                )
                .options(
                    selectinload(
                        ServiceConnection.work_entries
                    ),
                )
            )

            connection = session.scalar(statement)

            if connection is None:
                raise FileNotFoundError(
                    "Stik med id "
                    f"{service_connection_id} findes ikke."
                )

            return self._service_connection_to_dict(
                connection
            )

    def create_service_connection(
        self,
        stretch_id: int,
        external_id: str,
        *,
        position_m: Decimal | float | int | str,
        clock_position: str,
        sequence: int = 0,
        dimension_mm: int | None = None,
        material: str = "",
        active: bool = True,
        to_be_opened: bool = False,
        decommissioned: bool = False,
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Opretter ét fysisk stik på et stræk.
        """
        normalized_external_id = str(external_id).strip()
        normalized_clock_position = str(
            clock_position
        ).strip()

        if not normalized_external_id:
            raise ValueError(
                "Stikkets eksterne identitet må ikke være tom."
            )

        if not normalized_clock_position:
            raise ValueError(
                "Stikkets urretning må ikke være tom."
            )

        normalized_position = decimal_or_none(position_m)

        if normalized_position is None:
            raise ValueError(
                "Stikkets position skal angives."
            )

        with self._session_scope() as session:
            stretch = session.get(Stretch, stretch_id)

            if stretch is None:
                raise FileNotFoundError(
                    f"Stræk med id {stretch_id} findes ikke."
                )

            connection = ServiceConnection(
                stretch_id=stretch_id,
                external_id=normalized_external_id,
                sequence=int(sequence),
                position_m=normalized_position,
                clock_position=normalized_clock_position,
                dimension_mm=dimension_mm,
                material=str(material or "").strip(),
                active=bool(active),
                to_be_opened=bool(to_be_opened),
                decommissioned=bool(decommissioned),
                notes=str(notes or "").strip(),
                metadata_data=dict(metadata or {}),
            )

            session.add(connection)

            try:
                self._save_changes(session)
                session.refresh(connection)
            except IntegrityError as exc:
                self._rollback(session)
                raise ValueError(
                    "Der findes allerede et stik på strækket "
                    "med samme identitet eller samme position "
                    "og urretning."
                ) from exc
            except Exception:
                self._rollback(session)
                raise

            return self._service_connection_to_dict(
                connection
            )

    def update_service_connection(
        self,
        service_connection_id: int,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Opdaterer tilladte tekniske oplysninger på et stik.

        Ændring af fysisk placering bør normalt oprette et nyt stik,
        fordi DANDAS-identiteten dermed ændres.
        """
        allowed_fields = {
            "sequence",
            "dimension_mm",
            "material",
            "active",
            "to_be_opened",
            "decommissioned",
            "notes",
            "metadata",
        }

        with self._session_scope() as session:
            connection = session.get(
                ServiceConnection,
                service_connection_id,
            )

            if connection is None:
                raise FileNotFoundError(
                    "Stik med id "
                    f"{service_connection_id} findes ikke."
                )

            for key, value in updates.items():
                if key not in allowed_fields:
                    continue

                if key == "metadata":
                    connection.metadata_data = dict(
                        value or {}
                    )
                    continue

                if key in {
                    "active",
                    "to_be_opened",
                    "decommissioned",
                }:
                    setattr(connection, key, bool(value))
                    continue

                if key in {"sequence", "dimension_mm"}:
                    setattr(
                        connection,
                        key,
                        int(value) if value is not None else None,
                    )
                    continue

                setattr(
                    connection,
                    key,
                    str(value or "").strip(),
                )

            try:
                self._save_changes(session)
                session.refresh(connection)
            except Exception:
                self._rollback(session)
                raise

            return self._service_connection_to_dict(
                connection
            )

    def record_manhole_work(
        self,
        manhole_id: int,
        work_type: str,
        *,
        status: str = "planned",
        quantity: Decimal | float | int | str = 1,
        unit: str = "stk",
        performed_date: date | str | None = None,
        performed_by: str | None = None,
        team_id: str | None = None,
        decision_id: int | None = None,
        supersedes_work_id: int | None = None,
        source: str = "system",
        source_reference: str | None = None,
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Opretter en ny historisk arbejdspost på en brønd.
        """
        normalized_work_type = str(work_type).strip()

        if not normalized_work_type:
            raise ValueError(
                "Arbejdstype må ikke være tom."
            )

        normalized_quantity = decimal_or_none(quantity)

        if normalized_quantity is None:
            raise ValueError(
                "Mængde skal angives."
            )

        with self._session_scope() as session:
            manhole = session.get(Manhole, manhole_id)

            if manhole is None:
                raise FileNotFoundError(
                    f"Brønd med id {manhole_id} findes ikke."
                )

            work = ManholeWork(
                manhole_id=manhole_id,
                decision_id=decision_id,
                supersedes_work_id=supersedes_work_id,
                work_type=normalized_work_type,
                status=str(status or "planned").strip(),
                quantity=normalized_quantity,
                unit=str(unit or "stk").strip(),
                performed_date=date_or_none(performed_date),
                performed_by=(
                    str(performed_by).strip()
                    if performed_by
                    else None
                ),
                team_id=team_id,
                source=str(source or "system").strip(),
                source_reference=(
                    str(source_reference).strip()
                    if source_reference
                    else None
                ),
                notes=str(notes or "").strip(),
                metadata_data=dict(metadata or {}),
            )

            session.add(work)

            try:
                self._save_changes(session)
                session.refresh(work)
            except IntegrityError as exc:
                self._rollback(session)
                raise ValueError(
                    "Arbejdsregistreringen refererer til "
                    "en beslutning, et hold eller en tidligere "
                    "arbejdspost, som ikke findes."
                ) from exc
            except Exception:
                self._rollback(session)
                raise

            return self._manhole_work_to_dict(work)

    def record_service_connection_work(
        self,
        service_connection_id: int,
        work_type: str,
        *,
        status: str = "planned",
        quantity: Decimal | float | int | str = 1,
        unit: str = "stk",
        performed_date: date | str | None = None,
        performed_by: str | None = None,
        team_id: str | None = None,
        decision_id: int | None = None,
        supersedes_work_id: int | None = None,
        source: str = "system",
        source_reference: str | None = None,
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Opretter en ny historisk arbejdspost på et stik.
        """
        normalized_work_type = str(work_type).strip()

        if not normalized_work_type:
            raise ValueError(
                "Arbejdstype må ikke være tom."
            )

        normalized_quantity = decimal_or_none(quantity)

        if normalized_quantity is None:
            raise ValueError(
                "Mængde skal angives."
            )

        with self._session_scope() as session:
            connection = session.get(
                ServiceConnection,
                service_connection_id,
            )

            if connection is None:
                raise FileNotFoundError(
                    "Stik med id "
                    f"{service_connection_id} findes ikke."
                )

            work = ServiceConnectionWork(
                service_connection_id=service_connection_id,
                decision_id=decision_id,
                supersedes_work_id=supersedes_work_id,
                work_type=normalized_work_type,
                status=str(status or "planned").strip(),
                quantity=normalized_quantity,
                unit=str(unit or "stk").strip(),
                performed_date=date_or_none(performed_date),
                performed_by=(
                    str(performed_by).strip()
                    if performed_by
                    else None
                ),
                team_id=team_id,
                source=str(source or "system").strip(),
                source_reference=(
                    str(source_reference).strip()
                    if source_reference
                    else None
                ),
                notes=str(notes or "").strip(),
                metadata_data=dict(metadata or {}),
            )

            session.add(work)

            try:
                self._save_changes(session)
                session.refresh(work)
            except IntegrityError as exc:
                self._rollback(session)
                raise ValueError(
                    "Arbejdsregistreringen refererer til "
                    "en beslutning, et hold eller en tidligere "
                    "arbejdspost, som ikke findes."
                ) from exc
            except Exception:
                self._rollback(session)
                raise

            return self._service_connection_work_to_dict(
                work
            )

    @staticmethod
    def _require_project(
        session: Any,
        project_id: str,
    ) -> Project:
        project = session.get(Project, project_id)

        if project is None:
            raise FileNotFoundError(
                f"Projektet '{project_id}' findes ikke."
            )

        return project

    def _project_assets_to_dict(
        self,
        project: Project,
    ) -> dict[str, Any]:
        installations = []

        for installation in sorted(
            project.installations,
            key=lambda item: (
                item.sequence,
                item.installation_no,
            ),
        ):
            stretches = [
                self._stretch_to_dict(stretch)
                for stretch in sorted(
                    installation.stretches,
                    key=lambda item: item.sequence,
                )
            ]

            installations.append(
                {
                    "id": installation.id,
                    "installation_no": (
                        installation.installation_no
                    ),
                    "sequence": installation.sequence,
                    "active": installation.active,
                    "stretches": stretches,
                }
            )

        return {
            "project_id": project.id,
            "project_name": project.name,
            "manholes": [
                self._manhole_to_dict(manhole)
                for manhole in sorted(
                    project.manholes,
                    key=lambda item: item.manhole_no,
                )
            ],
            "installations": installations,
        }

    def _stretch_to_dict(
        self,
        stretch: Stretch,
    ) -> dict[str, Any]:
        return {
            "id": stretch.id,
            "installation_id": stretch.installation_id,
            "sequence": stretch.sequence,
            "bottom_manhole_id": stretch.bottom_manhole_id,
            "top_manhole_id": stretch.top_manhole_id,
            "bottom_manhole_no": (
                stretch.bottom_manhole.manhole_no
                if stretch.bottom_manhole
                else stretch.from_brond
            ),
            "top_manhole_no": (
                stretch.top_manhole.manhole_no
                if stretch.top_manhole
                else stretch.to_brond
            ),
            "from_brond": stretch.from_brond,
            "to_brond": stretch.to_brond,
            "length_m": stretch.length_m,
            "dimension": stretch.dimension,
            "material": stretch.material,
            "stik": stretch.stik,
            "notes": stretch.notes,
            "metadata": dict(
                stretch.metadata_data or {}
            ),
            "service_connections": [
                self._service_connection_to_dict(connection)
                for connection in sorted(
                    stretch.service_connections,
                    key=lambda item: (
                        item.sequence,
                        item.position_m,
                    ),
                )
            ],
        }

    def _manhole_to_dict(
        self,
        manhole: Manhole,
    ) -> dict[str, Any]:
        return {
            "id": manhole.id,
            "project_id": manhole.project_id,
            "manhole_no": manhole.manhole_no,
            "diameter_m": (
                float(manhole.diameter_m)
                if manhole.diameter_m is not None
                else None
            ),
            "depth_m": (
                float(manhole.depth_m)
                if manhole.depth_m is not None
                else None
            ),
            "profile": manhole.profile,
            "material": manhole.material,
            "active": manhole.active,
            "notes": manhole.notes,
            "metadata": dict(
                manhole.metadata_data or {}
            ),
            "work_entries": [
                self._manhole_work_to_dict(work)
                for work in manhole.work_entries
            ],
        }

    def _service_connection_to_dict(
        self,
        connection: ServiceConnection,
    ) -> dict[str, Any]:
        return {
            "id": connection.id,
            "stretch_id": connection.stretch_id,
            "external_id": connection.external_id,
            "sequence": connection.sequence,
            "position_m": float(connection.position_m),
            "clock_position": connection.clock_position,
            "dimension_mm": connection.dimension_mm,
            "material": connection.material,
            "active": connection.active,
            "to_be_opened": connection.to_be_opened,
            "decommissioned": connection.decommissioned,
            "notes": connection.notes,
            "metadata": dict(
                connection.metadata_data or {}
            ),
            "work_entries": [
                self._service_connection_work_to_dict(work)
                for work in connection.work_entries
            ],
        }

    @staticmethod
    def _manhole_work_to_dict(
        work: ManholeWork,
    ) -> dict[str, Any]:
        return {
            "id": work.id,
            "manhole_id": work.manhole_id,
            "decision_id": work.decision_id,
            "supersedes_work_id": work.supersedes_work_id,
            "work_type": work.work_type,
            "status": work.status,
            "quantity": float(work.quantity),
            "unit": work.unit,
            "performed_date": (
                work.performed_date.isoformat()
                if work.performed_date
                else None
            ),
            "performed_by": work.performed_by,
            "team_id": work.team_id,
            "source": work.source,
            "source_reference": work.source_reference,
            "notes": work.notes,
            "metadata": dict(
                work.metadata_data or {}
            ),
            "created_at": work.created_at.isoformat(),
            "updated_at": work.updated_at.isoformat(),
        }

    @staticmethod
    def _service_connection_work_to_dict(
        work: ServiceConnectionWork,
    ) -> dict[str, Any]:
        return {
            "id": work.id,
            "service_connection_id": (
                work.service_connection_id
            ),
            "decision_id": work.decision_id,
            "supersedes_work_id": work.supersedes_work_id,
            "work_type": work.work_type,
            "status": work.status,
            "quantity": float(work.quantity),
            "unit": work.unit,
            "performed_date": (
                work.performed_date.isoformat()
                if work.performed_date
                else None
            ),
            "performed_by": work.performed_by,
            "team_id": work.team_id,
            "source": work.source,
            "source_reference": work.source_reference,
            "notes": work.notes,
            "metadata": dict(
                work.metadata_data or {}
            ),
            "created_at": work.created_at.isoformat(),
            "updated_at": work.updated_at.isoformat(),
        }