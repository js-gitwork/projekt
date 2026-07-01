import json
from datetime import date, timedelta

from core.ai_assistent import ask_mistral_fast


ALLOWED_FIELDS = {
    "project_id",
    "name",
    "customer",
    "city",
    "start_date",
    "installation_count",
    "preparation_team",
}


def clean_ai_value(value):
    if value in [None, ""]:
        return None

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return None

        if value.lower() in ["null", "none", "ukendt", "ikke oplyst"]:
            return None

    return value


def normalize_project_id(value):
    value = clean_ai_value(value)

    if not value:
        return None

    value = str(value).strip().upper()

    if not value.startswith("V"):
        return None

    if len(value) < 2 or not value[1].isdigit():
        return None

    return value


def normalize_installation_count(value):
    value = clean_ai_value(value)

    if value is None:
        return None

    try:
        number = int(value)
    except (TypeError, ValueError):
        return None

    if number < 1:
        return None

    return number


def normalize_start_date(value):
    value = clean_ai_value(value)

    if not value:
        return None

    value = str(value).strip()

    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def parse_project_creation_request(text, default_year=None):
    default_year = default_year or date.today().year

    today = date.today()
    tomorrow = today + timedelta(days=1)

    prompt = f"""
Du skal udtrække projektoplysninger fra brugerens tekst.

Returnér KUN gyldig JSON.
Ingen forklaring.
Ingen markdown.
Hvis et felt er uklart, mangler eller kun kan gættes, skal værdien være null.
Gæt aldrig.

Felter:
- project_id
- name
- customer
- city
- start_date
- installation_count
- preparation_team

Regler:
- project_id er et V-nummer, fx V165930.
- name er projektnavn/sagsnavn.
- customer er kunden/bygherren.
- city er by, område eller lokation.
- Hvis city ikke er tydeligt angivet, brug null.
- Hvis name og city ikke tydeligt er det samme, må du ikke kopiere name til city.
- start_date skal være ISO-format YYYY-MM-DD.
- Hvis brugeren skriver "i dag", brug datoen {today.isoformat()}.
- Hvis brugeren skriver "i morgen", brug datoen {tomorrow.isoformat()}.
- Hvis brugeren nævner en dato uden årstal, brug år {default_year}.
- installation_count skal være et heltal.
- preparation_team må kun udfyldes, hvis et konkret hold er nævnt.
- Tekst om opmåling er ikke et holdnavn.
- Tekst om opmåling kan godt være årsagen til start_date, men skal ikke bruges som city.

Brugerens tekst:
{text}

Returnér præcis dette JSON-format:
{{
  "project_id": null,
  "name": null,
  "customer": null,
  "city": null,
  "start_date": null,
  "installation_count": null,
  "preparation_team": null
}}
"""

    raw_answer = ask_mistral_fast(prompt)

    try:
        ai_data = json.loads(raw_answer)
    except json.JSONDecodeError:
        return {}

    return {
        "project_id": normalize_project_id(ai_data.get("project_id")),
        "name": clean_ai_value(ai_data.get("name")),
        "customer": clean_ai_value(ai_data.get("customer")),
        "city": clean_ai_value(ai_data.get("city")),
        "start_date": normalize_start_date(ai_data.get("start_date")),
        "installation_count": normalize_installation_count(
            ai_data.get("installation_count")
        ),
        "preparation_team": clean_ai_value(ai_data.get("preparation_team")),
    }