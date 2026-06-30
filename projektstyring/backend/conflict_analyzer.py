from collections import defaultdict


def activity_date_range(activity):
    start = activity.get("start")
    end = activity.get("end")

    if not start or not end:
        return []

    if start == end:
        return [start]

    return [start, end]


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

    return conflicts


def summarize_conflicts(conflicts):
    return {
        "conflict_count": len(conflicts),
        "affected_teams": sorted({
            conflict["team"]
            for conflict in conflicts
        }),
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
