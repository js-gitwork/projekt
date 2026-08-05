from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from projektstyring.backend.change_analyzer import (
    compare_states,
)
from projektstyring.backend.database.connection import (
    SessionLocal,
)
from projektstyring.backend.db_models import Decision
from projektstyring.backend.repositories.decision_repository import (
    DecisionRepository,
)
from projektstyring.backend.snapshot_service import (
    get_latest_snapshot,
)


decision_repository = DecisionRepository()


def datetime_to_string(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def decision_to_dict(
    decision: Decision,
) -> dict[str, Any]:
    return {
        "id": decision.id,
        "project_id": decision.project_id,
        "decision_type": decision.decision_type,
        "status": decision.status,
        "trigger": decision.trigger,
        "reason": decision.reason,
        "requested_by": decision.requested_by,
        "approved_by": decision.approved_by,
        "approved_at": datetime_to_string(
            decision.approved_at
        ),
        "committed_at": datetime_to_string(
            decision.committed_at
        ),
        "change_set": deepcopy(
            decision.change_set or {}
        ),
        "simulation_result": deepcopy(
            decision.simulation_result or {}
        ),
        "metadata": deepcopy(
            decision.metadata_data or {}
        ),
        "created_at": datetime_to_string(
            decision.created_at
        ),
    }


def build_project_insight(
    project: dict[str, Any],
) -> dict[str, Any]:
    """
    Samler projektets databasebaserede historik i én struktur,
    som Roerbot kan bruge.

    Baselines er snapshots med snapshot_type='baseline'.
    Beslutninger hentes fra decisions-tabellen.
    """
    project_id = str(
        project.get("id") or ""
    ).strip()

    if not project_id:
        raise ValueError(
            "Projektet mangler projekt-id."
        )

    baseline = get_latest_snapshot(
        project_id,
        snapshot_type="baseline",
    )

    latest_snapshot = get_latest_snapshot(
        project_id,
    )

    insight: dict[str, Any] = {
        "project_id": project_id,
        "status": project.get("status"),
        "has_baseline": baseline is not None,
        "baseline_version": (
            baseline.get("version")
            if baseline
            else None
        ),
        "latest_snapshot_version": (
            latest_snapshot.get("version")
            if latest_snapshot
            else None
        ),
        "changes_since_baseline": [],
        "changes_since_latest_snapshot": [],
        "decision_count": 0,
        "latest_decision": None,
    }

    if baseline:
        baseline_state = (
            baseline.get("project_state")
            or {}
        )

        insight["changes_since_baseline"] = (
            compare_states(
                baseline_state,
                project,
            ).get(
                "installation_changes",
                [],
            )
        )

    if latest_snapshot:
        latest_state = (
            latest_snapshot.get("project_state")
            or {}
        )

        insight[
            "changes_since_latest_snapshot"
        ] = compare_states(
            latest_state,
            project,
        ).get(
            "installation_changes",
            [],
        )

    with SessionLocal() as session:
        decisions = (
            decision_repository.list_for_project(
                session=session,
                project_id=project_id,
            )
        )

        insight["decision_count"] = len(
            decisions
        )

        if decisions:
            insight["latest_decision"] = (
                decision_to_dict(
                    decisions[0]
                )
            )

    return insight