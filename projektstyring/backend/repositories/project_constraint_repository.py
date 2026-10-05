from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import (
    Project,
    ProjectConstraint,
)


def date_or_none(
    value: date | str | None,
) -> date | None:
    if value in (None, ""):
        return None

    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value))


class ProjectConstraintRepository:
    """
    Databaseadgang til projektets frister og rådighedsperioder.

    Constraints er faktagrundlag for Rørbot og watchdog-funktioner.
    De er ikke en del af den normale planlægningsmotor.

    Typiske constraint-typer:
    - availability_permit
    - project_deadline
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
                select(ProjectConstraint)
                .where(
                    ProjectConstraint.project_id
                    == normalized_project_id
                )
                .order_by(
                    ProjectConstraint.end_date.asc().nulls_last(),
                    ProjectConstraint.constraint_type.asc(),
                    ProjectConstraint.reference.asc(),
                )
            )

            constraints = session.scalars(statement).all()

            return [
                self._constraint_to_dict(constraint)
                for constraint in constraints
            ]

    def list_by_type(
        self,
        project_id: str,
        constraint_type: str,
    ) -> list[dict[str, Any]]:
        normalized_project_id = str(project_id).strip()
        normalized_type = str(constraint_type).strip()

        with self._session_scope() as session:
            self._require_project(
                session,
                normalized_project_id,
            )

            statement = (
                select(ProjectConstraint)
                .where(
                    ProjectConstraint.project_id
                    == normalized_project_id,
                    ProjectConstraint.constraint_type
                    == normalized_type,
                )
                .order_by(
                    ProjectConstraint.end_date.asc().nulls_last(),
                    ProjectConstraint.reference.asc(),
                )
            )

            constraints = session.scalars(statement).all()

            return [
                self._constraint_to_dict(constraint)
                for constraint in constraints
            ]

    def get_nearest_end_date(
        self,
        project_id: str,
        constraint_type: str,
        *,
        from_date: date | None = None,
    ) -> dict[str, Any] | None:
        normalized_project_id = str(project_id).strip()
        normalized_type = str(constraint_type).strip()

        with self._session_scope() as session:
            self._require_project(
                session,
                normalized_project_id,
            )

            statement = (
                select(ProjectConstraint)
                .where(
                    ProjectConstraint.project_id
                    == normalized_project_id,
                    ProjectConstraint.constraint_type
                    == normalized_type,
                    ProjectConstraint.end_date.is_not(None),
                )
            )

            if from_date is not None:
                statement = statement.where(
                    ProjectConstraint.end_date >= from_date
                )

            statement = statement.order_by(
                ProjectConstraint.end_date.asc(),
                ProjectConstraint.reference.asc(),
            )

            constraint = session.scalar(statement)

            if constraint is None:
                return None

            return self._constraint_to_dict(
                constraint
            )

    def upsert(
        self,
        *,
        project_id: str,
        constraint_type: str,
        reference: str = "",
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        source: str = "manual",
        source_reference: str | None = None,
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Opretter eller opdaterer en constraint idempotent.

        Identiteten er:

            project_id + constraint_type + reference

        Returnerer:
        {
            "action": "created" | "updated" | "unchanged",
            "constraint": {...}
        }
        """

        normalized_project_id = str(project_id).strip()
        normalized_type = str(constraint_type).strip()
        normalized_reference = str(reference or "").strip()
        normalized_source = str(source or "").strip()
        normalized_source_reference = (
            str(source_reference).strip()
            if source_reference not in (None, "")
            else None
        )
        normalized_notes = str(notes or "").strip()
        normalized_metadata = dict(metadata or {})

        if not normalized_project_id:
            raise ValueError("Projekt-id skal angives.")

        if not normalized_type:
            raise ValueError(
                "Constraint-type skal angives."
            )

        values = {
            "start_date": date_or_none(
                start_date
            ),
            "end_date": date_or_none(
                end_date
            ),
            "source": normalized_source,
            "source_reference": (
                normalized_source_reference
            ),
            "notes": normalized_notes,
            "metadata_data": normalized_metadata,
        }

        with self._session_scope() as session:
            self._require_project(
                session,
                normalized_project_id,
            )

            constraint = session.scalar(
                select(ProjectConstraint).where(
                    ProjectConstraint.project_id
                    == normalized_project_id,
                    ProjectConstraint.constraint_type
                    == normalized_type,
                    ProjectConstraint.reference
                    == normalized_reference,
                )
            )

            if constraint is None:
                constraint = ProjectConstraint(
                    project_id=normalized_project_id,
                    constraint_type=normalized_type,
                    reference=normalized_reference,
                    **values,
                )

                session.add(constraint)

                try:
                    self._save_changes(session)
                    session.refresh(constraint)

                except IntegrityError as exc:
                    self._rollback(session)

                    raise ValueError(
                        "Constraint kunne ikke oprettes: "
                        f"{normalized_project_id}/"
                        f"{normalized_type}/"
                        f"{normalized_reference}."
                    ) from exc

                except Exception:
                    self._rollback(session)
                    raise

                return {
                    "action": "created",
                    "constraint": self._constraint_to_dict(
                        constraint
                    ),
                }

            changed = False

            for field_name, new_value in values.items():
                old_value = getattr(
                    constraint,
                    field_name,
                )

                if old_value == new_value:
                    continue

                setattr(
                    constraint,
                    field_name,
                    new_value,
                )
                changed = True

            if not changed:
                return {
                    "action": "unchanged",
                    "constraint": self._constraint_to_dict(
                        constraint
                    ),
                }

            try:
                self._save_changes(session)
                session.refresh(constraint)

            except Exception:
                self._rollback(session)
                raise

            return {
                "action": "updated",
                "constraint": self._constraint_to_dict(
                    constraint
                ),
            }

    def upsert_availability_permit(
        self,
        *,
        project_id: str,
        permit_number: str,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        permit_week: str | int | None = None,
        source_reference: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        permit_number_normalized = str(
            permit_number or ""
        ).strip()

        combined_metadata = dict(metadata or {})

        if permit_week not in (None, ""):
            combined_metadata["permit_week"] = str(
                permit_week
            ).strip()

        return self.upsert(
            project_id=project_id,
            constraint_type="availability_permit",
            reference=permit_number_normalized,
            start_date=start_date,
            end_date=end_date,
            source="c5",
            source_reference=source_reference,
            metadata=combined_metadata,
        )

    def upsert_project_deadline(
        self,
        *,
        project_id: str,
        deadline: date | str,
        source_reference: str | None = None,
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.upsert(
            project_id=project_id,
            constraint_type="project_deadline",
            reference="",
            end_date=deadline,
            source="project_manager",
            source_reference=source_reference,
            notes=notes,
            metadata=metadata,
        )

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
    def _constraint_to_dict(
        constraint: ProjectConstraint,
    ) -> dict[str, Any]:
        return {
            "id": constraint.id,
            "project_id": constraint.project_id,
            "constraint_type": constraint.constraint_type,
            "reference": constraint.reference,
            "start_date": constraint.start_date,
            "end_date": constraint.end_date,
            "source": constraint.source,
            "source_reference": (
                constraint.source_reference
            ),
            "notes": constraint.notes,
            "metadata": dict(
                constraint.metadata_data or {}
            ),
            "created_at": constraint.created_at,
            "updated_at": constraint.updated_at,
        }
