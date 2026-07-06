from datetime import datetime


def create_decision(
    *,
    decision_type,
    reason,
    trigger="manual",
    affected_installations=None,
    metadata=None,
):
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "type": decision_type,
        "trigger": trigger,
        "reason": reason,
        "affected_installations": affected_installations or [],
        "metadata": metadata or {},
    }


def add_decision(
    project,
    *,
    decision_type,
    reason,
    trigger="manual",
    affected_installations=None,
    metadata=None,
):
    project.setdefault("decisions", [])

    project["decisions"].append(
        create_decision(
            decision_type=decision_type,
            reason=reason,
            trigger=trigger,
            affected_installations=affected_installations,
            metadata=metadata,
        )
    )

    return project


def get_decisions(project):
    return project.get("decisions", [])


def get_latest_decision(project):
    decisions = get_decisions(project)

    if not decisions:
        return None

    return decisions[-1]
