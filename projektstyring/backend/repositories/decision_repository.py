from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from projektstyring.backend.db_models import (
    Decision,
    DecisionChange,
)


class DecisionRepository:
    def create(
        self,
        *,
        session: Session,
        project_id: str,
        decision_type: str,
        change_set: dict[str, Any],
        simulation_result: dict[str, Any] | None = None,
        reason: str = "",
        trigger: str = "manual",
        requested_by: str | None = None,
        approved_by: str | None = None,
        status: str = "simulated",
        metadata: dict[str, Any] | None = None,
    ) -> Decision:
        """
        Opretter en beslutning i den eksisterende transaktion.

        Funktionen kalder ikke commit. Den kaldende service bestemmer,
        om hele beslutningsforløbet skal gemmes eller rulles tilbage.
        """
        decision = Decision(
            project_id=project_id,
            decision_type=decision_type,
            status=status,
            trigger=trigger,
            reason=reason,
            requested_by=requested_by,
            approved_by=approved_by,
            change_set=change_set,
            simulation_result=simulation_result or {},
            metadata_data=metadata or {},
        )

        session.add(decision)
        session.flush()

        self._create_change_rows(
            session=session,
            decision=decision,
            change_set=change_set,
        )

        session.flush()

        return decision

    def get(
        self,
        *,
        session: Session,
        decision_id: int,
    ) -> Decision | None:
        return session.scalar(
            select(Decision)
            .where(Decision.id == decision_id)
            .options(
                selectinload(Decision.changes),
                selectinload(Decision.snapshots),
            )
        )

    def get_latest(
        self,
        *,
        session: Session,
        project_id: str,
    ) -> Decision | None:
        return session.scalar(
            select(Decision)
            .where(Decision.project_id == project_id)
            .options(
                selectinload(Decision.changes),
                selectinload(Decision.snapshots),
            )
            .order_by(Decision.created_at.desc())
            .limit(1)
        )

    def list_for_project(
        self,
        *,
        session: Session,
        project_id: str,
    ) -> list[Decision]:
        return list(
            session.scalars(
                select(Decision)
                .where(
                    Decision.project_id == project_id
                )
                .options(
                    selectinload(Decision.changes),
                )
                .order_by(
                    Decision.created_at.desc()
                )
            )
        )

    def mark_approved(
        self,
        *,
        decision: Decision,
        approved_by: str,
        approved_at,
    ) -> None:
        decision.status = "approved"
        decision.approved_by = approved_by
        decision.approved_at = approved_at

    def mark_committed(
        self,
        *,
        decision: Decision,
        committed_at,
    ) -> None:
        decision.status = "committed"
        decision.committed_at = committed_at

    def mark_failed(
        self,
        *,
        decision: Decision,
        error_message: str,
    ) -> None:
        decision.status = "failed"

        metadata = dict(
            decision.metadata_data or {}
        )
        metadata["error"] = error_message

        decision.metadata_data = metadata

    def _create_change_rows(
        self,
        *,
        session: Session,
        decision: Decision,
        change_set: dict[str, Any],
    ) -> None:
        changes = self._normalize_changes(
            change_set
        )

        for sequence, change in enumerate(
            changes,
            start=1,
        ):
            session.add(
                DecisionChange(
                    decision_id=decision.id,
                    sequence=sequence,
                    change_type=str(
                        change.get("change_type")
                        or change.get("type")
                        or decision.decision_type
                    ),
                    target_type=str(
                        change.get("target_type")
                        or self._infer_target_type(
                            change
                        )
                    ),
                    target_id=self._infer_target_id(
                        change
                    ),
                    before_data=self._dictionary_or_none(
                        change.get("before")
                    ),
                    after_data=self._dictionary_or_none(
                        change.get("after")
                    ),
                    metadata_data={
                        key: value
                        for key, value in change.items()
                        if key
                        not in {
                            "change_type",
                            "type",
                            "target_type",
                            "target_id",
                            "before",
                            "after",
                        }
                    },
                )
            )

    @staticmethod
    def _normalize_changes(
        change_set: dict[str, Any],
    ) -> list[dict[str, Any]]:
        changes = change_set.get("changes")

        if isinstance(changes, list):
            return [
                item
                for item in changes
                if isinstance(item, dict)
            ]

        return [change_set]

    @staticmethod
    def _infer_target_type(
        change: dict[str, Any],
    ) -> str:
        if change.get("installation_id"):
            return "installation"

        if change.get("installation_ids"):
            return "installation_group"

        if change.get("team"):
            return "team_assignment"

        if change.get("task_type"):
            return "project_task"

        return "project"

    @staticmethod
    def _infer_target_id(
        change: dict[str, Any],
    ) -> str | None:
        explicit_target = change.get("target_id")

        if explicit_target not in (None, ""):
            return str(explicit_target)

        installation_id = change.get(
            "installation_id"
        )

        if installation_id not in (None, ""):
            return str(installation_id)

        installation_ids = change.get(
            "installation_ids"
        )

        if isinstance(installation_ids, list):
            return ",".join(
                str(value)
                for value in installation_ids
            )

        team = change.get("team")

        if team not in (None, ""):
            return str(team)

        task_type = change.get("task_type")

        if task_type not in (None, ""):
            return str(task_type)

        return None

    @staticmethod
    def _dictionary_or_none(
        value: Any,
    ) -> dict[str, Any] | None:
        if value is None:
            return None

        if isinstance(value, dict):
            return value

        return {
            "value": value,
        }
