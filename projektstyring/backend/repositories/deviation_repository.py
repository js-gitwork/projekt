from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import (
    Deviation,
    Installation,
    Manhole,
    Project,
)


def date_or_none(
    value: date | str | None,
) -> date | None:
    if value in (None, ""):
        return None

    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value))


class DeviationRepository:
    """
    Databaseadgang til projektets afvigelser.

    Afvigelser er hændelsesoprettet arbejde og indgår ikke
    i den almindelige produktionsplan.

    C5-identiteten er:

        project_id + deviation_number

    Repository'et understøtter idempotent import:
    - ny afvigelse       -> created
    - ændrede oplysninger -> updated
    - identiske oplysninger -> unchanged
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
        if self._session is not None:
            yield self._session
            return

        with SessionLocal() as session:
            yield session

    def get_by_project_and_number(
        self,
        project_id: str,
        deviation_number: str,
    ) -> dict[str, Any]:
        normalized_project_id = str(project_id).strip()
        normalized_number = str(deviation_number).strip()

        with self._session_scope() as session:
            deviation = session.scalar(
                select(Deviation).where(
                    Deviation.project_id == normalized_project_id,
                    Deviation.deviation_number == normalized_number,
                )
            )

            if deviation is None:
                raise FileNotFoundError(
                    "Afvigelse "
                    f"'{normalized_number}' findes ikke "
                    f"på projekt '{normalized_project_id}'."
                )

            return self._deviation_to_dict(deviation)

    def list_for_project(
        self,
        project_id: str,
    ) -> list[dict[str, Any]]:
        normalized_project_id = str(project_id).strip()

        with self._session_scope() as session:
            self._require_project(
                session,
                normalized_project_id,
            )

            statement = (
                select(Deviation)
                .where(
                    Deviation.project_id == normalized_project_id
                )
                .order_by(
                    Deviation.reported_date.asc().nulls_last(),
                    Deviation.deviation_number.asc(),
                )
            )

            deviations = session.scalars(statement).all()

            return [
                self._deviation_to_dict(deviation)
                for deviation in deviations
            ]

    def list_open_for_project(
        self,
        project_id: str,
    ) -> list[dict[str, Any]]:
        """
        Afvigelser hvor selve udbedringen endnu ikke er registreret
        som udført.

        Manglende godkendelse behandles separat og gør ikke i sig
        selv reparationsarbejdet åbent.
        """
        normalized_project_id = str(project_id).strip()

        with self._session_scope() as session:
            self._require_project(
                session,
                normalized_project_id,
            )

            statement = (
                select(Deviation)
                .where(
                    Deviation.project_id == normalized_project_id,
                    Deviation.completed_date.is_(None),
                )
                .order_by(
                    Deviation.reported_date.asc().nulls_last(),
                    Deviation.deviation_number.asc(),
                )
            )

            deviations = session.scalars(statement).all()

            return [
                self._deviation_to_dict(deviation)
                for deviation in deviations
            ]

    def list_pending_approval_for_project(
        self,
        project_id: str,
    ) -> list[dict[str, Any]]:
        """
        Afvigelser der er udført, men endnu ikke godkendt.
        """
        normalized_project_id = str(project_id).strip()

        with self._session_scope() as session:
            self._require_project(
                session,
                normalized_project_id,
            )

            statement = (
                select(Deviation)
                .where(
                    Deviation.project_id == normalized_project_id,
                    Deviation.completed_date.is_not(None),
                    Deviation.approved_date.is_(None),
                )
                .order_by(
                    Deviation.completed_date.asc(),
                    Deviation.deviation_number.asc(),
                )
            )

            deviations = session.scalars(statement).all()

            return [
                self._deviation_to_dict(deviation)
                for deviation in deviations
            ]

    def upsert_from_c5(
        self,
        *,
        project_id: str,
        deviation_number: str,
        installation_no: str | None = None,
        bottom_manhole_no: str | None = None,
        top_manhole_no: str | None = None,
        dimension_mm: int | str | None = None,
        deviation_type: str = "",
        description: str = "",
        reported_date: date | str | None = None,
        completed_date: date | str | None = None,
        completed_by: str | None = None,
        approved_date: date | str | None = None,
        source_reference: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Opretter eller opdaterer en C5-afvigelse idempotent.

        Installation og brønde opløses ud fra deres forretnings-
        identiteter. Hvis en relation ikke kan opløses, gemmes
        afvigelsen stadig; relationen bliver blot NULL.

        Returnerer:
        {
            "action": "created" | "updated" | "unchanged",
            "deviation": {...}
        }
        """

        normalized_project_id = str(project_id).strip()
        normalized_number = str(deviation_number).strip()

        if not normalized_project_id:
            raise ValueError("Projekt-id skal angives.")

        if not normalized_number:
            raise ValueError("Afvigelsesnummer skal angives.")

        normalized_installation_no = (
            str(installation_no).strip()
            if installation_no not in (None, "")
            else None
        )

        normalized_bottom = (
            str(bottom_manhole_no).strip()
            if bottom_manhole_no not in (None, "")
            else None
        )

        normalized_top = (
            str(top_manhole_no).strip()
            if top_manhole_no not in (None, "")
            else None
        )

        normalized_dimension = self._int_or_none(
            dimension_mm
        )

        normalized_type = str(
            deviation_type or ""
        ).strip()

        normalized_description = str(
            description or ""
        ).strip()

        normalized_completed_by = (
            str(completed_by).strip()
            if completed_by not in (None, "")
            else None
        )

        normalized_source_reference = (
            str(source_reference).strip()
            if source_reference not in (None, "")
            else None
        )

        normalized_metadata = dict(metadata or {})

        with self._session_scope() as session:
            self._require_project(
                session,
                normalized_project_id,
            )

            installation = self._find_installation(
                session,
                normalized_project_id,
                normalized_installation_no,
            )

            bottom_manhole = self._find_manhole(
                session,
                normalized_project_id,
                normalized_bottom,
            )

            top_manhole = self._find_manhole(
                session,
                normalized_project_id,
                normalized_top,
            )

            values = {
                "installation_id": (
                    installation.id
                    if installation is not None
                    else None
                ),
                "bottom_manhole_id": (
                    bottom_manhole.id
                    if bottom_manhole is not None
                    else None
                ),
                "top_manhole_id": (
                    top_manhole.id
                    if top_manhole is not None
                    else None
                ),
                "dimension_mm": normalized_dimension,
                "deviation_type": normalized_type,
                "description": normalized_description,
                "reported_date": date_or_none(
                    reported_date
                ),
                "completed_date": date_or_none(
                    completed_date
                ),
                "completed_by": normalized_completed_by,
                "approved_date": date_or_none(
                    approved_date
                ),
                "source": "c5",
                "source_reference": (
                    normalized_source_reference
                ),
                "metadata_data": normalized_metadata,
            }

            deviation = session.scalar(
                select(Deviation).where(
                    Deviation.project_id
                    == normalized_project_id,
                    Deviation.deviation_number
                    == normalized_number,
                )
            )

            if deviation is None:
                deviation = Deviation(
                    project_id=normalized_project_id,
                    deviation_number=normalized_number,
                    **values,
                )

                session.add(deviation)

                try:
                    self._save_changes(session)
                    session.refresh(deviation)

                except IntegrityError as exc:
                    self._rollback(session)

                    raise ValueError(
                        "Afvigelsen kunne ikke oprettes: "
                        f"{normalized_project_id}/"
                        f"{normalized_number}."
                    ) from exc

                except Exception:
                    self._rollback(session)
                    raise

                return {
                    "action": "created",
                    "deviation": self._deviation_to_dict(
                        deviation
                    ),
                }

            changed = False

            for field_name, new_value in values.items():
                old_value = getattr(
                    deviation,
                    field_name,
                )

                if old_value == new_value:
                    continue

                setattr(
                    deviation,
                    field_name,
                    new_value,
                )
                changed = True

            if not changed:
                return {
                    "action": "unchanged",
                    "deviation": self._deviation_to_dict(
                        deviation
                    ),
                }

            try:
                self._save_changes(session)
                session.refresh(deviation)

            except Exception:
                self._rollback(session)
                raise

            return {
                "action": "updated",
                "deviation": self._deviation_to_dict(
                    deviation
                ),
            }

    @staticmethod
    def _require_project(
        session: Session,
        project_id: str,
    ) -> Project:
        project = session.get(
            Project,
            project_id,
        )

        if project is None:
            raise FileNotFoundError(
                f"Projekt '{project_id}' findes ikke."
            )

        return project

    @staticmethod
    def _find_installation(
        session: Session,
        project_id: str,
        installation_no: str | None,
    ) -> Installation | None:
        if not installation_no:
            return None

        return session.scalar(
            select(Installation).where(
                Installation.project_id == project_id,
                Installation.installation_no
                == installation_no,
            )
        )

    @staticmethod
    def _find_manhole(
        session: Session,
        project_id: str,
        manhole_no: str | None,
    ) -> Manhole | None:
        if not manhole_no:
            return None

        return session.scalar(
            select(Manhole).where(
                Manhole.project_id == project_id,
                Manhole.manhole_no == manhole_no,
            )
        )

    @staticmethod
    def _int_or_none(
        value: int | str | None,
    ) -> int | None:
        if value in (None, ""):
            return None

        if isinstance(value, int):
            return value

        text = str(value).strip()

        if not text:
            return None

        return int(float(text.replace(",", ".")))

    @staticmethod
    def _deviation_to_dict(
        deviation: Deviation,
    ) -> dict[str, Any]:
        installation = getattr(
            deviation,
            "installation",
            None,
        )

        bottom_manhole = getattr(
            deviation,
            "bottom_manhole",
            None,
        )

        top_manhole = getattr(
            deviation,
            "top_manhole",
            None,
        )

        return {
            "id": deviation.id,
            "project_id": deviation.project_id,
            "deviation_number": deviation.deviation_number,

            "installation_id": deviation.installation_id,
            "installation_no": (
            str(installation.installation_no)
                if installation is not None
                else None
            ),

            "bottom_manhole_id": deviation.bottom_manhole_id,
            "bottom_manhole_no": (
                str(bottom_manhole.manhole_no)
                if bottom_manhole is not None
                else None
            ),

            "top_manhole_id": deviation.top_manhole_id,
            "top_manhole_no": (
                str(top_manhole.manhole_no)
                if top_manhole is not None
                else None
            ),

            "dimension_mm": deviation.dimension_mm,
            "deviation_type": deviation.deviation_type,
            "description": deviation.description,
            "reported_date": deviation.reported_date,
            "completed_date": deviation.completed_date,
            "completed_by": deviation.completed_by,
            "approved_date": deviation.approved_date,
            "source": deviation.source,
            "source_reference": deviation.source_reference,
            "metadata": dict(
                deviation.metadata_data or {}
            ),
            "created_at": deviation.created_at,
            "updated_at": deviation.updated_at,
        }