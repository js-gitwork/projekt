import re
from datetime import date, timedelta


def extract_project_id(text):
    for word in text.replace(",", " ").replace(".", " ").split():
        cleaned = word.strip().upper()
        if cleaned.startswith("V") and any(char.isdigit() for char in cleaned):
            return cleaned
    return None


def extract_project_id_or_alias(text):
    project_id = extract_project_id(text)

    if project_id:
        return project_id

    if "herslev" in text.lower():
        return "V165460"

    return None


def extract_week_deadline(text, year=2026):
    match = re.search(r"uge\s*(\d+)", text.lower())

    if not match:
        return None

    week = int(match.group(1))
    monday = date.fromisocalendar(year, week, 1)
    sunday = monday + timedelta(days=6)

    return sunday.isoformat()


def infer_team(text, intent=None):
    intent = intent or {}

    if intent.get("team"):
        return intent["team"]

    compact = text.lower().replace(" ", "")

    known_teams = [
        "stik1",
        "stik2",
        "tv11",
        "tv22",
        "tv22oe_dtvk",
        "hat3",
        "broend1",
        "broend2",
        "filt_oest",
    ]

    for team in known_teams:
        if team.lower() in compact:
            return team

    return None


def infer_task_type(text, team=None, intent=None):
    intent = intent or {}

    if intent.get("task_type"):
        return intent["task_type"]

    lower = text.lower()

    if "dtvk" in lower:
        return "dtvk"

    if "korthat" in lower or "hat" in lower:
        return "korthat"

    if "brønd" in lower or "broend" in lower:
        return "brønd"

    if "stikforberedelse" in lower:
        return "stikforberedelse"

    if "stik" in lower:
        return "stik"

    if "hovedledning" in lower:
        return "hovedledning"

    if team:
        team_lower = team.lower()

        if team_lower.startswith("stik"):
            return "stik"

        if team_lower.startswith("tv"):
            return "kontrol"

        if team_lower.startswith("hat"):
            return "korthat"

        if team_lower.startswith("broend") or team_lower.startswith("brønd"):
            return "brønd"

        if "filt" in team_lower:
            return "hovedledning"

    return None


def infer_before_task_type(task_type):
    workflow_dependencies = {
        "hovedledning": "forarbejde",
        "stikforberedelse": None,
        "stik": "hovedledning",
        "kontrol": "stik",
        "korthat": "stik",
        "brønd": "korthat",
        "dtvk": "brønd",
    }

    return workflow_dependencies.get(task_type)


def infer_reason(text, intent=None):
    intent = intent or {}

    if intent.get("reason"):
        return intent["reason"]

    original = text.strip()
    lower = original.lower()

    reason = None

    if " fordi " in lower:
        index = lower.index(" fordi ") + len(" fordi ")
        reason = original[index:].strip()
    elif " da " in lower:
        index = lower.index(" da ") + len(" da ")
        reason = original[index:].strip()

    if not reason:
        return None

    cleanup_phrases = [
        "kan du foreslå en løsning?",
        "kan du foreslå en løsning",
        "hvordan kan vi lade dem blive det?",
        "hvordan kan vi lade dem blive det",
        "hvordan kan vi løse det?",
        "hvordan kan vi løse det",
    ]

    reason_lower = reason.lower()

    for phrase in cleanup_phrases:
        if phrase in reason_lower:
            start = reason_lower.index(phrase)
            reason = reason[:start].strip()
            reason_lower = reason.lower()

    return reason.rstrip(".?").strip()


def build_decision_data(question, intent=None):
    intent = intent or {}

    project_id = extract_project_id_or_alias(question)
    team = infer_team(question, intent)
    task_type = infer_task_type(question, team, intent)
    deadline = intent.get("deadline") or extract_week_deadline(question)

    before_task_type = (
        intent.get("before_task_type")
        or infer_before_task_type(task_type)
    )

    reason = infer_reason(question, intent)

    return {
        "intent": intent,
        "original_question": question,
        "project_id": project_id,
        "team": team,
        "task_type": task_type,
        "before_task_type": before_task_type,
        "deadline": deadline,
        "reason": reason,
    }
