INSTALLATION_FIELDS = [
    "active",
    "hoveddato",
    "expected_stik",
    "active_stik",
    "langhatte",
    "korthatte_extra",
    "broende",
    "notes",
]


def _installation_map(state):
    return {
        str(installation.get("id")): installation
        for installation in state.get("installations", [])
    }


def compare_installations(before, after):
    changes = []

    before_map = _installation_map(before)
    after_map = _installation_map(after)

    all_ids = sorted(
        set(before_map.keys()) | set(after_map.keys()),
        key=lambda value: int(value) if value.isdigit() else value,
    )

    for installation_id in all_ids:
        before_installation = before_map.get(installation_id)
        after_installation = after_map.get(installation_id)

        if before_installation is None:
            changes.append({
                "type": "installation_added",
                "installation_id": installation_id,
                "after": after_installation,
            })
            continue

        if after_installation is None:
            changes.append({
                "type": "installation_removed",
                "installation_id": installation_id,
                "before": before_installation,
            })
            continue

        for field in INSTALLATION_FIELDS:
            before_value = before_installation.get(field)
            after_value = after_installation.get(field)

            if before_value != after_value:
                changes.append({
                    "type": "installation_changed",
                    "installation_id": installation_id,
                    "field": field,
                    "before": before_value,
                    "after": after_value,
                })

    return changes


def compare_states(before, after):
    return {
        "from": before.get("created_at"),
        "to": after.get("created_at"),
        "project_id": after.get("project_id") or after.get("id"),
        "installation_changes": compare_installations(before, after),
    }


def compare_timeline(states):
    timeline = []

    for index in range(len(states) - 1):
        timeline.append(
            compare_states(
                states[index],
                states[index + 1],
            )
        )

    return timeline
