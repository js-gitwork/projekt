from projektstyring.backend.baseline_service import has_baseline
from projektstyring.backend.change_analyzer import compare_states
from projektstyring.backend.snapshot_service import get_latest_snapshot
from projektstyring.backend.decision_log import get_decisions


def build_project_insight(project):
    """
    Samler projektets historik og analyser i én struktur,
    som Roerbot kan bruge som grundlag for sine svar.
    """

    insight = {
        "project_id": project.get("id"),
        "status": project.get("status"),
        "has_baseline": has_baseline(project),
        "changes_since_baseline": [],
        "changes_since_latest_snapshot": [],
        "decision_count": 0,
        "latest_decision": None,
    }

    if has_baseline(project):
        baseline = project["baseline"]
        insight["changes_since_baseline"] = compare_states(
            baseline,
            project,
        )["installation_changes"]

    latest_snapshot = get_latest_snapshot(project)

    if latest_snapshot:
        insight["changes_since_latest_snapshot"] = compare_states(
            latest_snapshot,
            project,
        )["installation_changes"]

    decisions = get_decisions(project)

    insight["decision_count"] = len(decisions)

    if decisions:
        insight["latest_decision"] = decisions[-1]

    return insight
