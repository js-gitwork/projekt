from collections import defaultdict
from datetime import date

from projektstyring.backend.conflict_analyzer import summarize_conflicts


def activity_key(activity):
    return (
        str(activity.get("installation_id")),
        str(activity.get("type")),
        str(activity.get("team")),
    )


def index_activities(activities):
    return {
        activity_key(activity): activity
        for activity in activities
    }


def group_changes_by_team(changes):
    grouped = defaultdict(list)

    for change in changes:
        team = change.get("team") or "ukendt"
        grouped[team].append(change)

    return dict(grouped)


def summarize_team_changes(changes):
    """
    Opsummerer påvirkningen pr. hold.

    days_moved angiver den største forskydning for én aktivitet.
    Forskydninger må ikke lægges sammen på tværs af aktiviteter,
    da det giver et misvisende samlet antal dage.
    """

    summary = {}

    for change in changes:
        team = change.get("team") or "ukendt"

        if team not in summary:
            summary[team] = {
                "activities": 0,
                "days_moved": 0,
            }

        summary[team]["activities"] += 1

        before = change.get("before_start")
        after = change.get("after_start")

        if before and after:
            try:
                before_date = date.fromisoformat(
                    before
                )
                after_date = date.fromisoformat(
                    after
                )

                activity_days_moved = abs(
                    (after_date - before_date).days
                )

                summary[team]["days_moved"] = max(
                    summary[team]["days_moved"],
                    activity_days_moved,
                )

            except ValueError:
                pass

    return dict(sorted(summary.items()))


def summarize_activity_type_changes(changes):
    summary = {}

    for change in changes:
        activity_type = change.get("type") or "ukendt"

        if activity_type not in summary:
            summary[activity_type] = {
                "activities": 0,
                "teams": set(),
            }

        summary[activity_type]["activities"] += 1

        if change.get("team"):
            summary[activity_type]["teams"].add(change["team"])

    result = {}

    for activity_type, data in summary.items():
        result[activity_type] = {
            "activities": data["activities"],
            "teams": sorted(data["teams"]),
            "team_count": len(data["teams"]),
        }

    return dict(sorted(result.items()))


def summarize_affected_period(changes, added, removed):
    dates = []

    for change in changes:
        dates.extend([
            change.get("before_start"),
            change.get("before_end"),
            change.get("after_start"),
            change.get("after_end"),
        ])

    for activity in added + removed:
        dates.extend([
            activity.get("start"),
            activity.get("end"),
        ])

    valid_dates = sorted({
        value
        for value in dates
        if value
    })

    return {
        "first_date": valid_dates[0] if valid_dates else None,
        "last_date": valid_dates[-1] if valid_dates else None,
    }


def summarize_affected_projects(project_id, conflict_summary):
    projects = {project_id}

    for conflict_project in conflict_summary.get("affected_projects", []):
        projects.add(conflict_project)

    direct_only = len(projects) == 1

    return {
        "projects": sorted(projects),
        "project_count": len(projects),
        "direct_only": direct_only,
    }


def compare_plans(before, after):
    before_index = index_activities(before)
    after_index = index_activities(after)

    changes = []
    added = []
    removed = []

    for key, after_activity in after_index.items():
        before_activity = before_index.get(key)

        if not before_activity:
            added.append(after_activity)
            continue

        if (
            before_activity.get("start") != after_activity.get("start")
            or before_activity.get("end") != after_activity.get("end")
        ):
            changes.append(
                {
                    "installation_id": after_activity.get("installation_id"),
                    "type": after_activity.get("type"),
                    "team": after_activity.get("team"),
                    "before_start": before_activity.get("start"),
                    "before_end": before_activity.get("end"),
                    "after_start": after_activity.get("start"),
                    "after_end": after_activity.get("end"),
                }
            )

    for key, before_activity in before_index.items():
        if key not in after_index:
            removed.append(before_activity)

    return {
        "changed": changes,
        "added": added,
        "removed": removed,
        "changed_by_team": group_changes_by_team(changes),
    }


def summarize_scenario(simulation_result):
    comparison = compare_plans(
        simulation_result["before"],
        simulation_result["after"],
    )

    changed = comparison["changed"]
    added = comparison["added"]
    removed = comparison["removed"]

    project_id = simulation_result["project_id"]

    team_summary = summarize_team_changes(changed)
    activity_type_summary = summarize_activity_type_changes(changed)

    affected_period = summarize_affected_period(
        changed,
        added,
        removed,
    )

    affected_teams = sorted({
        change["team"]
        for change in changed
        if change.get("team")
    })

    conflicts = simulation_result.get("conflicts", [])
    conflict_summary = summarize_conflicts(conflicts)

    affected_projects = summarize_affected_projects(
        project_id,
        conflict_summary,
    )

    return {
        "project_id": project_id,
        "change": simulation_result["change"],
        "saved": simulation_result["saved"],
        "summary": {
            "changed_activities": len(changed),
            "added_activities": len(added),
            "removed_activities": len(removed),
            "affected_teams": affected_teams,
            "affected_team_count": len(affected_teams),
        },
        "comparison": comparison,
        "team_summary": team_summary,
        "activity_type_summary": activity_type_summary,
        "affected_period": affected_period,
        "affected_projects": affected_projects,
        "conflicts": conflict_summary,
    }


def format_scenario_report(report):
    change = report["change"]
    summary = report["summary"]
    team_summary = report["team_summary"]
    activity_type_summary = report["activity_type_summary"]
    affected_period = report["affected_period"]
    affected_projects = report["affected_projects"]
    conflict_summary = report["conflicts"]

    lines = [
        f"Scenario for projekt {report['project_id']}",
        "",
        f"Ændring: {change['field']}",
        f"Fra: {change['from']}",
        f"Til: {change['to']}",
        "",
        "Konsekvenser:",
        f"• Ændrede aktiviteter: {summary['changed_activities']}",
        f"• Tilføjede aktiviteter: {summary['added_activities']}",
        f"• Fjernede aktiviteter: {summary['removed_activities']}",
        f"• Påvirkede hold: {summary['affected_team_count']}",
        f"• Berørte projekter: {affected_projects['project_count']}",
    ]

    if affected_period["first_date"] and affected_period["last_date"]:
        lines.append("")
        lines.append("Påvirket periode:")
        lines.append(
            f"• Første påvirkede dato: {affected_period['first_date']}"
        )
        lines.append(
            f"• Sidste påvirkede dato: {affected_period['last_date']}"
        )

    lines.append("")
    lines.append("Berørte projekter:")

    if affected_projects["direct_only"]:
        lines.append(
            f"• Kun {report['project_id']} påvirkes direkte."
        )
    else:
        for project_id in affected_projects["projects"]:
            lines.append(f"• {project_id}")

    if summary["affected_teams"]:
        lines.append("")
        lines.append("Påvirkede hold:")

        for team in summary["affected_teams"]:
            lines.append(f"• {team}")

    if activity_type_summary:
        lines.append("")
        lines.append("Ændringer pr. aktivitet:")

        for activity_type, data in activity_type_summary.items():
            lines.append(
                f"• {activity_type}: "
                f"{data['activities']} aktiviteter "
                f"på {data['team_count']} hold"
            )

    if team_summary:
        lines.append("")
        lines.append("Ændringer pr. hold:")

        for team, data in team_summary.items():
            lines.append(
                f"• {team}: "
                f"{data['activities']} aktiviteter "
                f"({data['days_moved']} dages forskydning)"
            )

    lines.append("")
    lines.append("Konflikter:")

    if conflict_summary["conflict_count"] == 0:
        lines.append("• Ingen holdkonflikter fundet.")
    else:
        lines.append(
            f"• Holdkonflikter: {conflict_summary['conflict_count']}"
        )
        lines.append(
            f"• Påvirkede hold: "
            f"{conflict_summary['affected_team_count']}"
        )
        lines.append(
            f"• Påvirkede projekter: "
            f"{conflict_summary['affected_project_count']}"
        )

        if conflict_summary["first_conflict_date"]:
            lines.append(
                f"• Første konflikt: "
                f"{conflict_summary['first_conflict_date']}"
            )

        if conflict_summary["last_conflict_date"]:
            lines.append(
                f"• Sidste konflikt: "
                f"{conflict_summary['last_conflict_date']}"
            )

        lines.append("")
        lines.append("Konfliktdetaljer:")

        for conflict in conflict_summary["conflicts"]:
            lines.append(
                f"• {conflict['date']} — {conflict['team']}: "
                f"{', '.join(conflict['projects'])}"
            )

    if not report["saved"]:
        lines.append("")
        lines.append("Scenarioet er ikke gemt.")

    return "\n".join(lines)