import re
from datetime import date, timedelta


DANISH_MONTHS = {
    "januar": 1,
    "februar": 2,
    "marts": 3,
    "april": 4,
    "maj": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}


DANISH_WEEKDAYS = {
    "mandag": 1,
    "tirsdag": 2,
    "onsdag": 3,
    "torsdag": 4,
    "fredag": 5,
    "lørdag": 6,
    "soendag": 7,
    "søndag": 7,
}


def normalize_text(text):
    return " ".join(text.strip().split())


def extract_project_id(text):
    match = re.search(r"\bV[\w\d]*\b", text, re.IGNORECASE)
    return match.group(0) if match else None


def extract_name(text):
    patterns = [
        r"med navnet\s+([A-Za-zÆØÅæøå0-9 \-/]+?)(?:\.|,| der er| startdato| start|$)",
        r"hedder\s+([A-Za-zÆØÅæøå0-9 \-/]+?)(?:\.|,| der er| startdato| start|$)",
        r"navn\s+([A-Za-zÆØÅæøå0-9 \-/]+?)(?:\.|,| der er| startdato| start|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    match = re.search(
        r"\bV[\w\d]+\b\s+([A-Za-zÆØÅæøå0-9 \-/]+?)(?:\s+med\s+\d+\s+installation|,|\.|$)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return None


def extract_installation_count(text):
    patterns = [
        r"der er\s+(\d+)\s+installation",
        r"med\s+(\d+)\s+installation",
        r"(\d+)\s+installation",
        r"installationer\s*[:=]?\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def extract_customer(text):
    patterns = [
        r"kunde(?:n)?\s+er\s+([A-Za-zÆØÅæøå0-9 &./-]+?)(?:\.|,| by| område| start| og vi|$)",
        r"for\s+([A-Za-zÆØÅæøå0-9 &./-]+?)(?:\.|,| i byen| i område| start| og vi|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value.lower().startswith("projekt"):
                continue
            return value

    return None


def extract_city(text):
    patterns = [
        r"by(?:en)?\s+er\s+([A-Za-zÆØÅæøå0-9 \-/]+?)(?:\.|,| kunde| start|$)",
        r"område(?:t)?\s+er\s+([A-Za-zÆØÅæøå0-9 \-/]+?)(?:\.|,| kunde| start|$)",
        r"i\s+([A-Za-zÆØÅæøå \-/]+?)(?:\.|,| kunde| start|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()

            if value.lower() in ["uge", "mandag", "tirsdag", "onsdag", "torsdag", "fredag"]:
                continue

            if "opmåling" in value.lower():
                continue

            return value

    name = extract_name(text)

    if name:
        return name

    return None


def extract_preparation_team(text):
    patterns = [
        r"forarbejde(?:t)?\s+(?:laves af|udføres af|skal laves af|hold)\s+([A-Za-zÆØÅæøå0-9_\-]+)",
        r"forarbejdshold(?:et)?\s+(?:er|skal være)?\s*([A-Za-zÆØÅæøå0-9_\-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def iso_weekday_date(year, week, weekday):
    return date.fromisocalendar(year, week, weekday).isoformat()


def extract_start_date(text, default_year=None):
    default_year = default_year or date.today().year
    today = date.today()

    lower = text.lower()

    if "i morgen" in lower:
        return (today + timedelta(days=1)).isoformat()

    if "i dag" in lower:
        return today.isoformat()

    iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if iso_match:
        return iso_match.group(1)

    dk_date_match = re.search(
        r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b",
        text,
    )
    if dk_date_match:
        day = int(dk_date_match.group(1))
        month = int(dk_date_match.group(2))
        year = int(dk_date_match.group(3))
        return date(year, month, day).isoformat()

    month_match = re.search(
        r"\b(\d{1,2})\.\s*([A-Za-zÆØÅæøå]+)\s*(20\d{2})?\b",
        text,
        re.IGNORECASE,
    )
    if month_match:
        day = int(month_match.group(1))
        month_name = month_match.group(2).lower()
        year = int(month_match.group(3)) if month_match.group(3) else default_year

        month = DANISH_MONTHS.get(month_name)
        if month:
            return date(year, month, day).isoformat()

    week_match = re.search(
        r"\b(mandag|tirsdag|onsdag|torsdag|fredag|lørdag|søndag|soendag)?\s*(?:i\s+)?uge\s+(\d{1,2})(?:\s+i\s+(20\d{2}))?\b",
        text,
        re.IGNORECASE,
    )
    if week_match:
        weekday_name = week_match.group(1)
        week = int(week_match.group(2))
        year = int(week_match.group(3)) if week_match.group(3) else default_year

        weekday = 1
        if weekday_name:
            weekday = DANISH_WEEKDAYS.get(weekday_name.lower(), 1)

        return iso_weekday_date(year, week, weekday)

    return None


def parse_project_creation_request(text, default_year=None):
    text = normalize_text(text)

    return {
        "project_id": extract_project_id(text),
        "name": extract_name(text),
        "customer": extract_customer(text),
        "city": extract_city(text),
        "start_date": extract_start_date(text, default_year=default_year),
        "installation_count": extract_installation_count(text),
        "preparation_team": extract_preparation_team(text),
    }