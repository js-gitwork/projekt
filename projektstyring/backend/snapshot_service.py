from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import ProjectSnapshot
from projektstyring.backend.repositories.snapshot_repository import (
    SnapshotRepository,
)


snapshot_repository = SnapshotRepository()


def datetime_to_string(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def date_to_string(
    value: date | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def snapshot_to_dict(
    snapshot: ProjectSnapshot,
) -> dict[str, Any]:
    """
    Serialiserer et snapshot, mens SQLAlchemy-sessionen stadig er aktiv.

    Resten af systemet modtager dermed almindelige Python-data og bliver
    ikke afhængigt af et SQLAlchemy-objekt, der senere kan være detached.
    """
    activities = []

    for activity in snapshot.plan_activities:
        activities.append(
            {
                "id": activity.id,
                "sequence": activity.sequence,
                "installation_no": (
                    activity.installation_no
                ),
                "task_type": activity.task_type,
                "team_id": activity.team_id,
                "start_date": date_to_string(
                    activity.start_date
                ),
                "end_date": date_to_string(
                    activity.end_date
                ),
                "status": activity.status,
                "quantities": deepcopy(
                    activity.quantities or {}
                ),
                "metadata": deepcopy(
                    activity.metadata_data or {}
                ),
            }
        )

    return {
        "id": snapshot.id,
        "project_id": snapshot.project_id,
        "decision_id": snapshot.decision_id,
        "version": snapshot.version,
        "snapshot_type": snapshot.snapshot_type,
        "phase": snapshot.phase,
        "reason": snapshot.reason,
        "approved_by": snapshot.approved_by,
        "project_state": deepcopy(
            snapshot.project_state
        ),
        "project_rules": deepcopy(
            snapshot.project_rules or []
        ),
        "calculated_plan": deepcopy(
            snapshot.calculated_plan or []
        ),
        "planner_version": snapshot.planner_version,
        "metadata": deepcopy(
            snapshot.metadata_data or {}
        ),
        "created_at": datetime_to_string(
            snapshot.created_at
        ),
        "plan_activities": activities,
    }


def create_snapshot(
    *,
    project_id: str,
    project_state: dict[str, Any],
    calculated_plan: list[dict[str, Any]] | None = None,
    reason: str = "manual",
    snapshot_type: str = "manual",
    phase: str = "standalone",
    decision_id: int | None = None,
    approved_by: str | None = None,
    planner_version: str = "current",
    metadata: dict[str, Any] | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """
    Gemmer et permanent projektsnapshot i PostgreSQL.

    Når der gives en eksisterende session:
    - snapshot'et deltager i den kaldende transaktion
    - funktionen udfører ikke commit eller rollback

    Uden en session:
    - funktionen opretter og afslutter selv transaktionen
    """
    owns_session = session is None
    database_session = session or SessionLocal()

    try:
        snapshot = snapshot_repository.create(
            session=database_session,
            project_id=project_id,
            project_state=deepcopy(
                project_state
            ),
            calculated_plan=deepcopy(
                calculated_plan or []
            ),
            reason=reason,
            snapshot_type=snapshot_type,
            phase=phase,
            decision_id=decision_id,
            approved_by=approved_by,
            planner_version=planner_version,
            metadata=deepcopy(
                metadata or {}
            ),
        )

        database_session.flush()

        result = snapshot_to_dict(snapshot)

        if owns_session:
            database_session.commit()

        return result

    except Exception:
        if owns_session:
            database_session.rollback()

        raise

    finally:
        if owns_session:
            database_session.close()


def get_snapshot(
    snapshot_id: str,
    *,
    session: Session | None = None,
) -> dict[str, Any] | None:
    owns_session = session is None
    database_session = session or SessionLocal()

    try:
        snapshot = snapshot_repository.get(
            session=database_session,
            snapshot_id=snapshot_id,
        )

        if snapshot is None:
            return None

        return snapshot_to_dict(snapshot)

    finally:
        if owns_session:
            database_session.close()


def get_latest_snapshot(
    project_id: str,
    *,
    snapshot_type: str | None = None,
    session: Session | None = None,
) -> dict[str, Any] | None:
    owns_session = session is None
    database_session = session or SessionLocal()

    try:
        snapshot = snapshot_repository.get_latest(
            session=database_session,
            project_id=project_id,
            snapshot_type=snapshot_type,
        )

        if snapshot is None:
            return None

        return snapshot_to_dict(snapshot)

    finally:
        if owns_session:
            database_session.close()


def list_snapshots(
    project_id: str,
    *,
    session: Session | None = None,
) -> list[dict[str, Any]]:
    owns_session = session is None
    database_session = session or SessionLocal()

    try:
        snapshots = (
            snapshot_repository.list_for_project(
                session=database_session,
                project_id=project_id,
            )
        )

        return [
            snapshot_to_dict(snapshot)
            for snapshot in snapshots
        ]

    finally:
        if owns_session:
            database_session.close()