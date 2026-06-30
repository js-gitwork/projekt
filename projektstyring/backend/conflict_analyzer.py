from collections import defaultdict
from datetime import date, timedelta


def parse_date(value):
    if not value:
        return None

    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def activity_date_range(activity):
    start = parse_date(activity.get("start"))
    end = parse_date(activity.get("end"))

    if not start or not end:
        return []

    if end < start:
        return []

    days = []
    current = start

    while current <= end:
        days.append(str(current))
        current += timedelta(days=1)

    return days


def build_team_day_index(plans):
    index = defaultdict(list)

    for project_id, activities in plans.items():
        for activity in activities:
            team = activity.get("team")

            if not team:
                continue

            for day in activity_date_range(activity):
                index[(team, day)].append(
                    {
                        "project_id": project_id,
                        "installation_id": activity.get("installation_id"),
                        "type": activity.get("type"),
                        "team": team,
                        "date": day,
                        "start": activity.get("start"),
                        "end": activity.get("end"),
                    }
                )

    return index


def find_team_conflicts(plans):
    index = build_team_day_index(plans)

    conflicts = []

    for (team, day), activities in index.items():
        project_ids = sorted({
            activity["project_id"]
            for activity in activities
        })

        if len(project_ids) <= 1:
            continue

        conflicts.append(
            {
                "team": team,
                "date": day,
                "projects": project_ids,
                "activities": activities,
            }
        )

    return sorted(
        conflicts,
        key=lambda conflict: (
            conflict["date"],
            conflict["team"],
        ),
    )


def summarize_conflicts(conflicts):
    affected_teams = sorted({
        conflict["team"]
        for conflict in conflicts
        if conflict.get("team")
    })

    affected_projects = sorted({
        project_id
        for conflict in conflicts
        for project_id in conflict.get("projects", [])
    })

    dates = sorted({
        conflict["date"]
        for conflict in conflicts
        if conflict.get("date")
    })

    return {
        "conflict_count": len(conflicts),
        "affected_teams": affected_teams,
        "affected_team_count": len(affected_teams),
        "affected_projects": affected_projects,
        "affected_project_count": len(affected_projects),
        "first_conflict_date": dates[0] if dates else None,
        "last_conflict_date": dates[-1] if dates else None,
        "conflicts": conflicts,
    }


def format_conflicts(conflicts):
    if not conflicts:
        return "Ingen holdkonflikter fundet."

    lines = [
        "Holdkonflikter:",
        "",
    ]

    for conflict in conflicts:
        lines.append(
            f"• {conflict['team']} er planlagt på flere projekter "
            f"den {conflict['date']}: "
            f"{', '.join(conflict['projects'])}"
        )

    return "\n".join(lines)