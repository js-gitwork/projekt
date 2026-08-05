from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from projektstyring.backend.db_models import (
    Project,
    ProjectSnapshot,
    SnapshotPlanActivity,
)


class SnapshotRepository:
    def create(
        self,
        *,
        session: Session,
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
    ) -> ProjectSnapshot:
        """
        Opretter et snapshot i den eksisterende transaktion.

        Funktionen kalder ikke commit. Den kaldende service bestemmer,
        om hele beslutningsforløbet skal committes eller rulles tilbage.
        """
        project = session.scalar(
            select(Project)
            .where(Project.id == project_id)
            .with_for_update()
        )

        if project is None:
            raise FileNotFoundError(
                f"Projektet '{project_id}' findes ikke."
            )

        latest_version = session.scalar(
            select(
                func.coalesce(
                    func.max(ProjectSnapshot.version),
                    0,
                )
            ).where(
                ProjectSnapshot.project_id == project_id
            )
        )

        version = int(latest_version or 0) + 1
        plan = calculated_plan or []

        snapshot = ProjectSnapshot(
            project_id=project_id,
            decision_id=decision_id,
            version=version,
            snapshot_type=snapshot_type,
            phase=phase,
            reason=reason,
            approved_by=approved_by,
            project_state=project_state,
            project_rules=list(
                project_state.get("project_rules") or []
            ),
            calculated_plan=plan,
            planner_version=planner_version,
            metadata_data=metadata or {},
        )

        session.add(snapshot)
        session.flush()

        for sequence, activity in enumerate(
            plan,
            start=1,
        ):
            session.add(
                SnapshotPlanActivity(
                    snapshot_id=snapshot.id,
                    project_id=project_id,
                    sequence=sequence,
                    installation_no=self._string_or_none(
                        activity.get("installation_id")
                        or activity.get("installation_no")
                    ),
                    task_type=str(
                        activity.get("type")
                        or activity.get("task_type")
                        or ""
                    ),
                    team_id=self._string_or_none(
                        activity.get("team")
                        or activity.get("team_id")
                    ),
                    start_date=self._date_value(
                        activity.get("start")
                        or activity.get("start_date")
                    ),
                    end_date=self._date_value(
                        activity.get("end")
                        or activity.get("end_date")
                    ),
                    status=str(
                        activity.get("status") or "planned"
                    ),
                    quantities=dict(
                        activity.get("quantities") or {}
                    ),
                    metadata_data={
                        key: value
                        for key, value in activity.items()
                        if key
                        not in {
                            "installation_id",
                            "installation_no",
                            "type",
                            "task_type",
                            "team",
                            "team_id",
                            "start",
                            "start_date",
                            "end",
                            "end_date",
                            "status",
                            "quantities",
                        }
                    },
                )
            )

        session.flush()

        return snapshot

    def get(
        self,
        *,
        session: Session,
        snapshot_id: str,
    ) -> ProjectSnapshot | None:
        return session.scalar(
            select(ProjectSnapshot)
            .where(ProjectSnapshot.id == snapshot_id)
            .options(
                selectinload(
                    ProjectSnapshot.plan_activities
                )
            )
        )

    def get_latest(
        self,
        *,
        session: Session,
        project_id: str,
        snapshot_type: str | None = None,
    ) -> ProjectSnapshot | None:
        statement = (
            select(ProjectSnapshot)
            .where(
                ProjectSnapshot.project_id == project_id
            )
            .options(
                selectinload(
                    ProjectSnapshot.plan_activities
                )
            )
            .order_by(
                ProjectSnapshot.version.desc()
            )
            .limit(1)
        )

        if snapshot_type:
            statement = statement.where(
                ProjectSnapshot.snapshot_type
                == snapshot_type
            )

        return session.scalar(statement)

    def list_for_project(
        self,
        *,
        session: Session,
        project_id: str,
    ) -> list[ProjectSnapshot]:
        return list(
            session.scalars(
                select(ProjectSnapshot)
                .where(
                    ProjectSnapshot.project_id
                    == project_id
                )
                .order_by(
                    ProjectSnapshot.version.desc()
                )
            )
        )

    @staticmethod
    def _string_or_none(
        value: Any,
    ) -> str | None:
        if value in (None, ""):
            return None

        return str(value)

    @staticmethod
    def _date_value(value):
        from datetime import date

        if value in (None, ""):
            return None

        if isinstance(value, date):
            return value

        return date.fromisoformat(str(value))
