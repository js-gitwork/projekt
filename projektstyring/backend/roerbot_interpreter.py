"""
Roerbot Interpreter
===================

Oversætter brugerens naturlige sprog til en struktureret hensigt.

Interpreteren må:
- forstå brugerens formulering
- identificere relevante projekter, hold og installationer
- beskrive nødvendige data til rapporter
- oversætte ønskede planændringer til changes[]
- normalisere relative datoer ud fra den aktuelle dato

Interpreteren må ikke:
- læse eller skrive databasen
- beregne planer eller konflikter
- godkende beslutninger
- påstå at en ændring er gennemført
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from core.ai_assistent import ask_mistral_fast


ALLOWED_INTENTS = {
    "report",
    "change",
    "project_creation",
    "general",
    "clarification",
    "production_status",
}

ALLOWED_RESOURCES = {
    "projects",
    "project",
    "installations",
    "tasks",
    "task_assignments",
    "teams",
    "calendars",
    "progress",
    "plan",
    "conflicts",
    "rest_work",
    "production_status",
    "decisions",
    "snapshots",
    "changes",
    "project_rules",
}

RESOURCE_DESCRIPTIONS = {
    "projects": (
        "Oversigt over projekter og deres centrale felter."
    ),
    "project": (
        "Komplette data for et eller flere konkrete projekter."
    ),
    "installations": (
        "Installationernes grunddata."
    ),
    "tasks": (
        "Projektets opgaver og opgavetyper."
    ),
    "task_assignments": (
        "Fordeling af opgaver på hold og installationer."
    ),
    "teams": (
        "Hold, deres navne og kompetencer."
    ),
    "calendars": (
        "Arbejds- og holdkalendere."
    ),
    "progress": (
        "Registreret fremdrift pr. installation."
    ),
    "plan": (
        "Den beregnede projektplan med aktiviteter og datoer."
    ),
    "conflicts": (
        "Konflikter og advarsler fra planmotoren."
    ),
    "rest_work": (
        "Restarbejde fra den beregnede plan."
    ),
    "production_status": (
        "Produktionsstatus baseret på tekniske databaseobjekter. "
        "Indeholder blandt andet udført, planlagt og manglende "
        "langhatte og korthatte samt manglende hovedstræk."
    ),
    "decisions": (
        "Gemte beslutninger."
    ),
    "snapshots": (
        "Gemte snapshots."
    ),
    "changes": (
        "Registrerede ændringer."
    ),
    "project_rules": (
        "Godkendte projektspecifikke regler."
    ),
}

ALLOWED_CHANGE_TYPES = {
    "project_field_change",
    "installation_field_change",
    "task_assignment_change",
}

ALLOWED_PROJECT_FIELDS = {
    "name",
    "customer",
    "city",
    "start_date",
    "planned_completion_date",
    "status",
    "notes",
}

ALLOWED_INSTALLATION_FIELDS = {
    "active",
    "hoveddato",
    "expected_stik",
    "active_stik",
    "langhatte",
    "korthatte_extra",
    "broende",
    "hovedledning_meter",
    "notes",
}


def default_interpretation(
    question: str,
) -> dict[str, Any]:
    """
    Returnerer en sikker standardfortolkning, hvis AI-outputtet fejler.
    """

    return {
        "intent": "general",
        "confidence": 0.0,
        "summary": question,
        "scope": {
            "project_ids": [],
            "installation_ids": [],
            "team_ids": [],
        },
        "data_requests": [],
        "changes": [],
        "analysis": {
            "type": "general_answer",
            "requires_engine": False,
        },
        "response": {
            "language": "da",
            "format": "brief",
        },
        "clarification": None,
    }


def extract_json_object(
    raw_answer: str,
) -> dict[str, Any] | None:
    """
    Finder ét JSON-objekt i modellens svar.

    Modellen bliver bedt om kun at returnere JSON, men funktionen
    tolererer tekst omkring objektet.
    """

    text = str(raw_answer or "").strip()

    if not text:
        return None

    try:
        result = json.loads(text)

        if isinstance(result, dict):
            return result

        return None

    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return None

    try:
        result = json.loads(
            text[start : end + 1]
        )

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        return None

    return None


def normalize_string_list(
    value: Any,
) -> list[str]:
    """
    Normaliserer modeloutput til en liste af unikke strenge.
    """

    if value is None:
        return []

    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        return []

    result = []

    for item in values:
        normalized = str(item or "").strip()

        if normalized and normalized not in result:
            result.append(normalized)

    return result


def normalize_scope(
    value: Any,
) -> dict[str, list[str]]:
    """
    Sikrer en ensartet scope-struktur.
    """

    scope = value if isinstance(value, dict) else {}

    return {
        "project_ids": normalize_string_list(
            scope.get("project_ids")
        ),
        "installation_ids": normalize_string_list(
            scope.get("installation_ids")
        ),
        "team_ids": normalize_string_list(
            scope.get("team_ids")
        ),
    }


def normalize_data_requests(
    value: Any,
) -> list[dict[str, Any]]:
    """
    Validerer AI'ens ønsker til rapportdata.
    """

    if not isinstance(value, list):
        return []

    result = []

    for request in value:
        if not isinstance(request, dict):
            continue

        resource = str(
            request.get("resource") or ""
        ).strip()

        if resource not in ALLOWED_RESOURCES:
            continue

        filters = request.get("filters")

        if not isinstance(filters, list):
            filters = []

        result.append(
            {
                "resource": resource,
                "filters": filters,
                "fields": normalize_string_list(
                    request.get("fields")
                ),
                "sort": (
                    request.get("sort")
                    if isinstance(
                        request.get("sort"),
                        dict,
                    )
                    else None
                ),
                "limit": request.get("limit"),
            }
        )

    return result


def normalize_change(
    value: Any,
) -> dict[str, Any] | None:
    """
    Validerer én foreslået planændring.

    Funktionen udfører ikke ændringen. Den sikrer kun, at AI-outputtet
    følger den kontrakt, ScenarioChangeApplier forventer.
    """

    if not isinstance(value, dict):
        return None

    change_type = str(
        value.get("change_type") or ""
    ).strip()

    if change_type not in ALLOWED_CHANGE_TYPES:
        return None

    project_id = str(
        value.get("project_id") or ""
    ).strip()

    if not project_id:
        return None

    after = value.get("after")

    if not isinstance(after, dict):
        return None

    grounding = value.get("grounding")

    if not isinstance(grounding, list):
        grounding = []

    normalized = {
        "change_type": change_type,
        "project_id": project_id,
        "reason": str(
            value.get("reason") or ""
        ).strip(),
        "metadata": (
            value.get("metadata")
            if isinstance(
                value.get("metadata"),
                dict,
            )
            else {}
        ),
        "after": dict(after),
        "grounding": [
            dict(item)
            for item in grounding
            if isinstance(item, dict)
        ],
    }
    if isinstance(value.get("before"), dict):
        normalized["before"] = dict(
            value["before"]
        )

    installation_id = value.get(
        "installation_id"
    )

    if installation_id is not None:
        normalized["installation_id"] = str(
            installation_id
        ).strip()

    target_id = value.get("target_id")

    if target_id is not None:
        normalized["target_id"] = str(
            target_id
        ).strip()

    options = value.get("options")

    if isinstance(options, dict):
        normalized["options"] = dict(options)

    if change_type == "project_field_change":
        field = str(
            after.get("field") or ""
        ).strip()

        if field not in ALLOWED_PROJECT_FIELDS:
            return None

        if (
            "value" not in after
            and field not in after
        ):
            return None

    if change_type == "installation_field_change":
        field = str(
            after.get("field") or ""
        ).strip()

        if field not in ALLOWED_INSTALLATION_FIELDS:
            return None

        if (
            "value" not in after
            and field not in after
        ):
            return None

        if not normalized.get(
            "installation_id"
        ) and not after.get(
            "installation_id"
        ):
            return None

    if change_type == "task_assignment_change":
        task_type = str(
            after.get("task_type") or ""
        ).strip()

        team_id = str(
            after.get("team_id")
            or after.get("team")
            or ""
        ).strip()

        if not task_type or not team_id:
            return None

        if not normalized.get(
            "installation_id"
        ) and not after.get(
            "installation_id"
        ):
            return None

    return normalized


def normalize_changes(
    value: Any,
) -> list[dict[str, Any]]:
    """
    Validerer et samlet ændringssæt.
    """

    if not isinstance(value, list):
        return []

    result = []

    for item in value:
        change = normalize_change(item)

        if change is not None:
            result.append(change)

    return result


def normalize_interpretation(
    question: str,
    value: dict[str, Any],
) -> dict[str, Any]:
    """
    Normaliserer og begrænser AI'ens strukturerede fortolkning.
    """

    intent = str(
        value.get("intent") or "general"
    ).strip()

    if intent not in ALLOWED_INTENTS:
        intent = "general"

    try:
        confidence = float(
            value.get("confidence", 0.0)
        )
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(
        0.0,
        min(1.0, confidence),
    )

    analysis = value.get("analysis")

    if not isinstance(analysis, dict):
        analysis = {}

    response = value.get("response")

    if not isinstance(response, dict):
        response = {}

    clarification = value.get("clarification")

    if not isinstance(clarification, dict):
        clarification = None

    changes = normalize_changes(
        value.get("changes")
    )

    if intent == "change" and not changes:
        intent = "clarification"

        if clarification is None:
            clarification = {
                "question": (
                    "Jeg kunne ikke udlede en sikker, "
                    "struktureret ændring."
                )
            }

    return {
        "intent": intent,
        "confidence": confidence,
        "summary": str(
            value.get("summary") or question
        ).strip(),
        "scope": normalize_scope(
            value.get("scope")
        ),
        "data_requests": normalize_data_requests(
            value.get("data_requests")
        ),
        "changes": changes,
        "analysis": {
            "type": str(
                analysis.get("type")
                or "general_answer"
            ).strip(),
            "requires_engine": bool(
                analysis.get(
                    "requires_engine",
                    intent == "change",
                )
            ),
        },
        "response": {
            "language": str(
                response.get("language") or "da"
            ).strip(),
            "format": str(
                response.get("format") or "brief"
            ).strip(),
        },
        "clarification": clarification,
    }


def build_interpreter_prompt(
    question: str,
    *,
    conversation_context: dict[str, Any] | None = None,
) -> str:
    """
    Bygger prompten til Roerbots sproglige fortolker.

    Interpreteren vælger ikke et Python-tool. Den beskriver enten:
    - hvilke data et rapportspørgsmål kræver
    - hvilke strukturerede ændringer brugeren ønsker
    """

    today = date.today()

    context_text = json.dumps(
        conversation_context or {},
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    return f"""
Du er Roerbots sproglige fortolker.

Din opgave er at forstå brugerens hensigt og oversætte den til en
struktureret arbejdsbeskrivelse.

Du udfører ikke ændringer.
Du læser ikke databasen.
Du beregner ikke planer.
Du må ikke påstå, at noget er gemt eller gennemført.

Aktuel dato:
{today.isoformat()}

Regler for datoer:
- "i år" betyder {today.year}
- "næste år" betyder {today.year + 1}
- "sidste år" betyder {today.year - 1}
- Relative datoer skal fortolkes ud fra den aktuelle dato.
- Konkrete datoer skal returneres som YYYY-MM-DD.
- Opfind aldrig et tilfældigt årstal.

- Brug altid source="question", når citatet findes i den aktuelle
  brugerbesked. Brug kun source="context", når værdien ikke står i
  brugerbeskeden, men er videreført fra den aktive samtalekontekst.

Mulige hensigter:
- report: brugeren ønsker data, overblik, analyse eller rapport
- change: brugeren ønsker at ændre eller revidere et scenarie
- project_creation: brugeren ønsker at oprette et projekt
- general: fagligt eller almindeligt spørgsmål
- clarification: nødvendige oplysninger mangler

Mulige rapportressourcer og deres betydning:
{json.dumps(
    RESOURCE_DESCRIPTIONS,
    indent=2,
    ensure_ascii=False,
)}

Format for hvert objekt i data_requests:

{{
    "resource": "navn på en tilladt resource",
    "filters": [
        {{
            "field": "feltnavn",
            "operator": "equals",
            "value": "værdi"
        }}
    ],
    "fields": [],
    "sort": {{
        "field": "feltnavn",
        "direction": "ascending"
    }},
    "limit": null
}}

Vigtige regler:

- Vælg resource ud fra dens beskrevne betydning og brugerens hensigt.
- filters skal ALTID være en liste.
- Hvert filter skal indeholde field, operator og value.
- sort skal være ét objekt eller null.
- Brug aldrig "sorting".
- Brug aldrig et dictionary direkte som filters.
- Hvis filtrering ikke er nødvendig, brug [].
- Hvis sortering ikke er nødvendig, brug null.
- Brug kun felter til filter og sortering, som findes direkte på den valgte resource.
- data_requests må kun indeholde ressourcer fra listen ovenfor.

Understøttede ændringstyper:
{json.dumps(
    sorted(ALLOWED_CHANGE_TYPES),
    indent=2,
    ensure_ascii=False,
)}

Tilladte projektfelter:
{json.dumps(
    sorted(ALLOWED_PROJECT_FIELDS),
    indent=2,
    ensure_ascii=False,
)}
    ensure_ascii=False,
)

Tilladte installationsfelter:
{json.dumps(
    sorted(ALLOWED_INSTALLATION_FIELDS),
    indent=2,
    ensure_ascii=False,
)}

Ændringskontrakter:

1. Ændring af projektfelt:

{{
  "change_type": "project_field_change",
  "project_id": "V165460",
  "after": {{
    "field": "start_date",
    "value": "2026-10-05"
  }},
  "grounding": [
    {{
      "target": "project_id",
      "quote": "V165460",
      "source": "question"
    }},
    {{
      "target": "field",
      "quote": "flyt",
      "source": "question"
    }},
    {{
      "target": "after.value",
      "quote": "5. oktober",
      "source": "question"
    }}
  ]
}}

2. Ændring af installationsfelt:

{{
  "change_type": "installation_field_change",
  "project_id": "V165460",
  "installation_id": "12",
  "after": {{
    "field": "hoveddato",
    "value": "2026-10-07"
  }}
}}

3. Flytning af en installationsopgave til et andet hold:

{{
  "change_type": "task_assignment_change",
  "project_id": "V165460",
  "installation_id": "12",
  "after": {{
    "task_type": "stik",
    "team_id": "stik1"
  }}
}}

Vigtige regler:
- Forstå betydningen semantisk og ikke kun gennem nøgleord.
- En besked kan indeholde flere ændringer.
- Hver ændring skal placeres som ét objekt i changes.
- Opfind aldrig projekt-id, installationsnummer eller hold.
- Hvis et nødvendigt projekt-id, installationsnummer, hold eller
  opgavetype mangler, brug intent="clarification".
- Brug intent="change" ved både nye forslag og revisioner af et
  eksisterende scenarie.
- Beskriv kun den ønskede nye tilstand.
- Du må ikke producere tool eller args.
- Hver ændring skal indeholde grounding.
- Grounding skal angive præcis hvilken tekst ændringens faktiske
  værdier er udledt af.
- quote skal være et ordret citat fra brugerens besked eller den
  leverede samtalekontekst.
- Brug source="question" for brugerens aktuelle besked.
- Brug source="context" kun når værdien faktisk står i konteksten.
- Du må ikke opfinde et grounding-citat.
- Hvis en nødvendig værdi ikke kan groundes, brug intent="clarification".
- Du må ikke producere godkendelse eller databasekommandoer.
- Rapporter skal bruge data_requests og normalt have changes=[].
- Ændringer skal bruge changes og have requires_engine=true.

Aktiv samtale- og scenariekontekst:
{context_text}

Returnér KUN ét gyldigt JSON-objekt.
Ingen markdown.
Ingen forklaring uden for JSON.

Svarformat:
{{
  "intent": "report | change | project_creation | general | clarification",
  "confidence": 0.0,
  "summary": "Kort beskrivelse af brugerens hensigt",
  "scope": {{
    "project_ids": [],
    "installation_ids": [],
    "team_ids": []
  }},
  "data_requests": [],
  "changes": [],
  "analysis": {{
    "type": "list | summary | comparison | risk_analysis | scenario_revision | general_answer",
    "requires_engine": false
  }},
  "response": {{
    "language": "da",
    "format": "brief | detailed | table | list"
  }},
  "clarification": null
}}

Brugerens besked:
{question}
""".strip()


def interpret_question(
    question: str,
    *,
    conversation_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Fortolker en besked og returnerer validerede Python-data.
    """

    normalized_question = str(
        question or ""
    ).strip()

    if not normalized_question:
        result = default_interpretation("")
        result["intent"] = "clarification"
        result["clarification"] = {
            "question": "Hvad vil du gerne vide eller ændre?"
        }
        return result

    prompt = build_interpreter_prompt(
        normalized_question,
        conversation_context=conversation_context,
    )

    raw_answer = ask_mistral_fast(prompt)

    print(
        "INTERPRETER RAW ANSWER:",
        raw_answer,
    )

    parsed = extract_json_object(
        raw_answer
    )

    if parsed is None:
        return default_interpretation(
            normalized_question
        )

    interpretation = normalize_interpretation(
        normalized_question,
        parsed,
    )

    print(
        "INTERPRETER RESULT:",
        interpretation,
    )

    return interpretation