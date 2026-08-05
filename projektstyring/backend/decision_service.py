from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.database.import_project import import_project
from projektstyring.backend.project_planner import generate_plan_for_project
from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.repositories.decision_repository import (
    DecisionRepository,
)
from projektstyring.backend.repositories.snapshot_repository import (
    SnapshotRepository,
)


project_repo = ProjectRepository()
decision_repo = DecisionRepository()
snapshot_repo = SnapshotRepository()


SUPPORTED_DECISION_TYPES = {
    "team_deadline_goal",
    "workflow_exception",
    "project_start_change",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_date(value) -> date | None:
    if not value:
        return None

    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value))


def summarize_plan(result) -> list[dict]:
    return [
        {
            "installation_id": str(activity.installation_id),
            "type": str(activity.type),
            "team": activity.hold,
            "start": (
                activity.start_dato.isoformat()
                if activity.start_dato
                else None
            ),
            "end": (
                activity.slut_dato.isoformat()
                if activity.slut_dato
                else None
            ),
            "status": getattr(
                activity,
                "status",
                "planned",
            ),
            "quantities": {
                "stik": getattr(
                    activity,
                    "antal_stik",
                    0,
                ),
                "broende": getattr(
                    activity,
                    "antal_brønde",
                    0,
                ),
                "hovedledning_meter": getattr(
                    activity,
                    "hovedledning_meter",
                    0,
                ),
            },
        }
        for activity in result.activities
    ]


def require_approved_by(
    approved_by: str | None,
) -> str:
    value = (approved_by or "").strip()

    if not value:
        raise ValueError(
            "Jeg kan ikke godkende ændringen uden navn "
            "på projektlederen."
        )

    return value


def build_project_rule(
    simulation: dict,
    approved_by: str,
) -> dict:
    change = deepcopy(
        simulation.get("change") or {}
    )

    return {
        "type": change.get("type"),
        "approved": True,
        "approved_by": approved_by,
        "approved_at": utc_now().isoformat(
            timespec="seconds"
        ),
        "source": "roerbot",
        "project_id": simulation.get("project_id"),
        "reason": change.get("reason"),
        "deadline": change.get("deadline"),
        "team": change.get("team"),
        "task_type": change.get("task_type"),
        "change": change,
    }


def apply_project_start_change(
    project: dict,
    change: dict,
) -> None:
    new_start = parse_date(
        change.get("to")
        or change.get("new_start_date")
    )

    if new_start is None:
        raise ValueError(
            "Beslutningen mangler en gyldig ny startdato."
        )

    old_start = parse_date(
        project.get("start_date")
    )

    if old_start is None:
        day_delta = int(
            change.get("day_delta") or 0
        )
    else:
        day_delta = (
            new_start - old_start
        ).days

    project["start_date"] = new_start.isoformat()

    for installation in project.get(
        "installations",
        [],
    ):
        hoveddato = parse_date(
            installation.get("hoveddato")
        )

        if hoveddato is None:
            continue

        installation["hoveddato"] = (
            hoveddato
            + timedelta(days=day_delta)
        ).isoformat()


def apply_rule_decision(
    project: dict,
    simulation: dict,
    approved_by: str,
) -> dict:
    rule = build_project_rule(
        simulation=simulation,
        approved_by=approved_by,
    )

    project.setdefault(
        "project_rules",
        [],
    )
    project["project_rules"].append(rule)

    return rule


def apply_simulation(
    project: dict,
    simulation: dict,
    approved_by: str,
) -> tuple[dict, dict]:
    updated_project = deepcopy(project)
    change = simulation.get("change") or {}
    decision_type = change.get("type")

    rule = apply_rule_decision(
        project=updated_project,
        simulation=simulation,
        approved_by=approved_by,
    )

    if decision_type == "project_start_change":
        apply_project_start_change(
            updated_project,
            change,
        )

    return updated_project, rule


def approve_simulation(
    simulation: dict,
    approved_by: str,
) -> dict:
    approved_by = require_approved_by(
        approved_by
    )

    if not simulation:
        raise ValueError(
            "Jeg mangler en simulation at godkende."
        )

    project_id = str(
        simulation.get("project_id") or ""
    ).strip()

    change = simulation.get("change") or {}
    decision_type = change.get("type")

    if not project_id:
        raise ValueError(
            "Simulationen mangler projekt-id."
        )

    if decision_type not in SUPPORTED_DECISION_TYPES:
        raise ValueError(
            "Beslutningstypen understøttes ikke: "
            f"{decision_type}"
        )

    original_project = (
        project_repo.load_project(project_id)
    )

    before_result = generate_plan_for_project(
        original_project
    )
    before_plan = summarize_plan(
        before_result
    )

    updated_project, rule = apply_simulation(
        project=original_project,
        simulation=simulation,
        approved_by=approved_by,
    )

    after_result = generate_plan_for_project(
        updated_project
    )
    after_plan = summarize_plan(
        after_result
    )

    approved_at = utc_now()

    with SessionLocal() as session:
        try:
            decision = decision_repo.create(
                session=session,
                project_id=project_id,
                decision_type=decision_type,
                change_set=change,
                simulation_result=simulation,
                reason=(
                    change.get("reason")
                    or "Godkendt Roerbot-beslutning"
                ),
                trigger="roerbot",
                approved_by=approved_by,
                status="approved",
                metadata={
                    "rule": rule,
                    "before_plan": before_plan,
                    "after_plan": after_plan,
                },
            )

            decision_repo.mark_approved(
                decision=decision,
                approved_by=approved_by,
                approved_at=approved_at,
            )

            snapshot_repo.create(
                session=session,
                project_id=project_id,
                project_state=original_project,
                calculated_plan=before_plan,
                reason=(
                    "Før godkendt beslutning "
                    f"#{decision.id}"
                ),
                snapshot_type="decision",
                phase="before",
                decision_id=decision.id,
                approved_by=approved_by,
                metadata={
                    "decision_type": decision_type,
                },
            )

            # Gemmer driftsdata som startdato og hoveddato.
            # Projektregler genopbygges fra decisions-tabellen.
            import_project(
                updated_project,
                session=session,
            )

            snapshot_repo.create(
                session=session,
                project_id=project_id,
                project_state=updated_project,
                calculated_plan=after_plan,
                reason=(
                    "Efter godkendt beslutning "
                    f"#{decision.id}"
                ),
                snapshot_type="decision",
                phase="after",
                decision_id=decision.id,
                approved_by=approved_by,
                metadata={
                    "decision_type": decision_type,
                },
            )

            decision_repo.mark_committed(
                decision=decision,
                committed_at=utc_now(),
            )

            session.flush()
            decision_id = int(decision.id)

            session.commit()

        except Exception:
            session.rollback()
            raise

    saved_project = project_repo.load_project(
        project_id
    )

    return {
        "ok": True,
        "decision_id": decision_id,
        "project": saved_project,
        "rule": rule,
        "before_plan": before_plan,
        "after_plan": after_plan,
        "answer": (
            f"Beslutning #{decision_id} er godkendt af "
            f"{approved_by} og gemt på projekt "
            f"{project_id}.\n\n"
            "Snapshot før og efter ændringen er gemt, "
            "planen er valideret, og hele ændringen er "
            "committet i én databasetransaktion."
        ),
    }
