from collections import defaultdict
from datetime import date

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
        grouped[change["team"]].append(change)

    return dict(grouped)

def summarize_team_changes(changes):
    summary = {}

    for change in changes:
        team = change["team"]

        if team not in summary:
            summary[team] = {
                "activities": 0,
                "days_moved": 0,
            }

        summary[team]["activities"] += 1

        before = change["before_start"]
        after = change["after_start"]

        if before and after:
            try:
                before_date = date.fromisoformat(before)
                after_date = date.fromisoformat(after)

                summary[team]["days_moved"] += abs(
                    (after_date - before_date).days
                )
            except ValueError:
                pass

    return summary


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

    team_summary = summarize_team_changes(
        comparison["changed"]
    )

    changed = comparison["changed"]
    added = comparison["added"]
    removed = comparison["removed"]

    affected_teams = sorted({
        change["team"]
        for change in changed
        if change.get("team")
    })

    return {
        "project_id": simulation_result["project_id"],
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
    }


def format_scenario_report(report):
    change = report["change"]
    summary = report["summary"]

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
    ]

    if summary["affected_teams"]:
        lines.append("")
        lines.append("Hold:")
        for team in summary["affected_teams"]:
            lines.append(f"• {team}")

        team_summary = report["team_summary"]

    if team_summary:
        lines.append("")
        lines.append("Ændringer pr. hold:")

        for team, data in team_summary.items():
            lines.append(
                f"• {team}: "
                f"{data['activities']} aktiviteter "
                f"({data['days_moved']} dages forskydning)"
            )

    return "\n".join(lines)
