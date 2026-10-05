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
    "scenario_decision",
}


ALLOWED_SCENARIO_DECISIONS = {
    "approve",
    "discard",
}

ALLOWED_PROJECT_CREATION_ACTIONS = {
    "update",
    "approve",
    "question",
    "cancel",
    "unrelated",
}

ALLOWED_PROJECT_CREATION_FIELDS = {
    "project_id",
    "name",
    "customer",
    "project_manager",
    "site_manager",
    "city",
    "start_date",
    "installation_count",
    "preparation_team",
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
    "remaining_work",
    "remaining_work_summary",
    "decisions",
    "snapshots",
    "changes",
    "project_rules",
    "project_constraints",
    "project_watchdog",
}

RESOURCE_DESCRIPTIONS = {
"projects": (
    "Oversigt over projekter og deres centrale projektfelter. "
    "Bruges ikke til at hente eller tælle installationer."
),
"project": (
    "Komplette projektdata for et eller flere konkrete projekter. "
    "Brug den relevante særskilte resource, når spørgsmålet handler "
    "om installationer, opgaver, fremdrift eller andre underdata."
),
"installations": (
    "Installationernes grunddata. Brug denne resource, når brugeren "
    "spørger om installationer, herunder hvilke installationer et "
    "projekt har eller hvor mange installationer der findes."
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
    "remaining_work": (
        "Normaliseret restarbejde pr. installation. "
        "Holder stik, langhat, korthat, brøndskud og "
        "punktreparationer adskilt og angiver deres "
        "produktionsgrupper. Ukendt status markeres "
        "eksplicit og gættes ikke."
    ),
    "remaining_work_summary": (
        "Kompakt status over restarbejde pr. opgavetype og "
        "installation. Skelner mellem dokumenteret restarbejde, "
        "ukendt status og dokumenteret færdigt arbejde. "
        "Brug denne til almindelige spørgsmål om hvad der mangler, "
        "hvad der er færdigt, og om et projekt er klar til næste trin."
    ),
    "project_constraints": (
        "Projektets faktuelle rammebetingelser og frister. "
        "Indeholder blandt andet rådighedstilladelser med "
        "tilladelsesnummer, gyldighedsperiode og hvilke "
        "installationer de dækker samt projektdeadline. "
        "Brug denne resource ved spørgsmål om tilladelser, "
        "frister, deadlines og andre projektconstraints."
    ),
    "project_watchdog": (
        "Deterministiske projektadvarsler beregnet af systemets "
        "watchdog. Indeholder aktuelle advarsler om blandt andet "
        "rådighedstilladelser, dokumenteret restarbejde, åbne "
        "afvigelser og projektdeadlines. Brug denne resource ved "
        "spørgsmål om risici, problemer, advarsler, forhold der "
        "kræver opmærksomhed, eller om der er noget på projektet "
        "man bør reagere på. AI'en skal ikke selv udlede disse "
        "advarsler fra rå projektdata."
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
    "manhole_field_change",
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

ALLOWED_MANHOLE_FIELDS = {
    "depth_m",
    "diameter_m",
    "profile",
    "material",
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
        "data_strategy": "none",
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

    manhole_no = value.get(
        "manhole_no"
    )

    if manhole_no is not None:
        normalized["manhole_no"] = str(
            manhole_no
        ).strip()

    target_id = value.get("target_id")

    if target_id is not None:
        normalized["target_id"] = str(
            target_id
        ).strip()

    options = value.get("options")

    if isinstance(options, dict):
        normalized["options"] = dict(options)

    selection = value.get("selection")

    if isinstance(selection, dict):
        selection_type = str(
            selection.get("type") or ""
        ).strip()

        if selection_type == "all":
            normalized["selection"] = {
                "type": "all",
            }

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

        has_installation_id = bool(
            normalized.get("installation_id")
            or after.get("installation_id")
        )

        selection = normalized.get(
            "selection"
        )

        has_valid_selection = (
            isinstance(selection, dict)
            and selection.get("type") == "all"
        )

        if (
            not has_installation_id
            and not has_valid_selection
        ):
            return None

    if change_type == "manhole_field_change":
        field = str(
            after.get("field") or ""
        ).strip()

        if field not in ALLOWED_MANHOLE_FIELDS:
            return None

        if (
            "value" not in after
            and field not in after
        ):
            return None

        if not normalized.get(
            "manhole_no"
        ) and not after.get(
            "manhole_no"
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

    scenario_decision = str(
        value.get("scenario_decision") or ""
    ).strip().lower()

    if scenario_decision not in ALLOWED_SCENARIO_DECISIONS:
        scenario_decision = None

    project_creation_action = str(
        value.get("project_creation_action") or ""
    ).strip().lower()

    if project_creation_action not in ALLOWED_PROJECT_CREATION_ACTIONS:
        project_creation_action = None

    raw_project_fields = value.get(
        "project_creation_fields"
    )

    if not isinstance(raw_project_fields, dict):
        raw_project_fields = {}

    project_creation_fields = {
        key: field_value
        for key, field_value in raw_project_fields.items()
        if key in ALLOWED_PROJECT_CREATION_FIELDS
        and field_value is not None
        and field_value != ""
        and not isinstance(field_value, (dict, list, bool))
    }

    # En besked med feltændringer må aldrig samtidig
    # udløse oprettelse af projektet.
    if (
        project_creation_action == "approve"
        and project_creation_fields
    ):
        project_creation_action = "update"

    if intent == "project_creation":
        if project_creation_action is None:
            project_creation_action = "question"

        if (
            project_creation_action == "update"
            and not project_creation_fields
        ):
            project_creation_action = "question"

    data_requests = normalize_data_requests(
        value.get("data_requests")
    )

    data_strategy = str(
        value.get("data_strategy")
        or ""
    ).strip()

    if data_strategy not in {
        "fetch",
        "reuse_context",
        "none",
    }:
        data_strategy = (
            "fetch"
            if data_requests
            else "none"
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

    if (
        intent == "scenario_decision"
        and scenario_decision is None
    ):
        intent = "clarification"

        if clarification is None:
            clarification = {
                "question": (
                    "Jeg kunne ikke afgøre sikkert, "
                    "om scenariet skal godkendes "
                    "eller kasseres."
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
        "data_strategy": data_strategy,
        "data_requests": data_requests,
        "scenario_decision": scenario_decision,
        "project_creation_action": project_creation_action,
        "project_creation_fields": project_creation_fields,
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
- scenario_decision: brugeren tager stilling til et allerede aktivt
  scenarieforslag
- project_creation: brugeren ønsker at oprette et projekt

Regler for igangværende projektoprettelse:

- Et aktivt projektudkast og et aktivt planlægningsscenarie
  er to forskellige workflows.

- Når workflow er "project_creation", og brugerens besked
  er et svar på det seneste spørgsmål om at oprette
  projektudkastet, skal intent være "project_creation".

- Et afslag på at oprette projektudkastet skal returneres
  som project_creation_action="cancel".
  Brug ikke intent="scenario_decision" til dette.

- En godkendelse af projektudkastet skal returneres som
  project_creation_action="approve", men kun når brugeren
  utvetydigt ønsker projektet oprettet.

- Fortolk svaret semantisk ud fra samtalekonteksten.
  Reglerne må ikke afhænge af en fast liste over
  bestemte ja- eller nej-formuleringer.

- Hvis samtalekontekstens workflow er "project_creation",
  findes der allerede et aktivt projektudkast.

- Fortolk brugerens nye besked i sammenhæng med dette udkast.

- Hvis brugeren besvarer et spørgsmål om projektet, skal
  intent være "project_creation".

- Et kort svar som "HTK" kan være et svar på det seneste
  spørgsmål om kunden. Brug samtalekonteksten til at afgøre det.

- Hvis brugeren supplerer eller korrigerer oplysninger om
  det aktive projekt, skal intent være "project_creation".

- Hvis brugeren spørger, hvilke projektoplysninger der
  mangler, eller beder om en oversigt over projektudkastet,
  skal intent også være "project_creation".

- Et spørgsmål om projektudkastet er ikke en ny feltværdi.

- Hvis brugeren stiller et selvstændigt spørgsmål, der ikke
  vedrører projektoprettelsen, skal den relevante almindelige
  intent anvendes. Et aktivt projektudkast må ikke overtage
  alle efterfølgende beskeder.

- Interpreteren må ikke selv oprette projektet eller ændre
  projektdata. Den beskriver alene brugerens hensigt.
- general: fagligt eller almindeligt spørgsmål
- clarification: nødvendige oplysninger mangler

Regler for beslutninger om aktive scenarier:

- Disse regler gælder kun planlægningsscenarier.
  De gælder aldrig godkendelse eller afvisning af
  et projektudkast under workflow="project_creation".

- Brug kun intent="scenario_decision", når der findes et aktivt
  scenarie i samtalekonteksten, og brugeren faktisk tager stilling
  til det fremlagte forslag.

- scenario_decision="approve" betyder, at brugeren accepterer det
  aktive forslag og ønsker det gennemført.

- scenario_decision="discard" betyder, at brugeren afviser eller
  opgiver det aktive forslag som helhed.

- Fortolk brugerens betydning semantisk. Beslutningen må ikke
  afhænge af bestemte nøgleord eller faste formuleringer.

- Hvis brugeren i stedet foreslår en anden værdi, dato, opgave,
  holdfordeling eller anden ændring til det eksisterende forslag,
  skal intent være "change", ikke "scenario_decision".

- Eksempel:
  "Nej, drop det forslag"
  betyder scenario_decision="discard".

- Eksempel:
  "Det ser fint ud, gennemfør det"
  betyder scenario_decision="approve".

- Eksempel:
  "Nej, sæt den i stedet til den 22."
  betyder intent="change", fordi brugeren reviderer forslaget.

- Interpreteren beskriver kun brugerens beslutning.
  Den må aldrig selv gennemføre, gemme, slette eller godkende data.

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
- Du ved ikke på forhånd, om de ønskede systemdata findes.
- Du må derfor aldrig vælge intent="clarification" alene fordi du
  antager, at en databaseværdi eller produktionsstatus mangler.
- Hvis brugerens spørgsmål kan besvares ved at hente en kendt
  rapportresource, skal du bruge intent="report" og bede om ressourcen.
- Det er Context Builder og Reporter, ikke Interpreteren, der afgør,
  om de hentede data faktisk er mangelfulde.
- Spørgsmål om manglende arbejde, resterende arbejde, færdigt eller
  ufærdigt produktionsarbejde skal normalt bruge
  resource="remaining_work_summary".
- Brug kun resource="remaining_work", når der er behov for den fulde
  interne restarbejdsstruktur til en særlig detaljeret analyse.
- Spørgsmål om rå udført/planlagt produktionsstatus kan bruge
  resource="production_status".
- Spørgsmål om rådighedstilladelser, tilladelsesnumre,
  tilladelsesperioder, hvilke installationer en tilladelse dækker,
  projektdeadline eller andre faktuelle projektfrister skal normalt
  bruge resource="project_constraints".
- Projektconstraints er faktuelle rammebetingelser og må ikke
  forveksles med datoer eller deadlines fra planlægningsmotoren.
- Spørgsmål om aktuelle risici, advarsler, problemer, forhold der
  kræver opmærksomhed, eller om der er noget på et projekt man bør
  være opmærksom på, skal normalt bruge
  resource="project_watchdog".
- project_watchdog indeholder deterministiske advarsler beregnet af
  systemet. Du må ikke selv forsøge at udlede de samme advarsler fra
  project_constraints, remaining_work, plan eller andre rå resources,
  når project_watchdog kan besvare spørgsmålet.
- Brug fortsat resource="project_constraints", når brugeren spørger
  efter de faktuelle oplysninger selv, eksempelvis en tilladelses
  nummer, gyldighedsperiode, dækkede installationer eller en
  projektdeadline.

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

Tilladte installationsfelter:
{json.dumps(
    sorted(ALLOWED_INSTALLATION_FIELDS),
    indent=2,
    ensure_ascii=False,
)}

Tilladte brøndfelter:
{json.dumps(
    sorted(ALLOWED_MANHOLE_FIELDS),
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

2a. Ændring af samme installationsfelt på alle installationer
i et projekt:

{{
  "change_type": "installation_field_change",
  "project_id": "V165460",
  "selection": {{
    "type": "all"
  }},
  "after": {{
    "field": "hoveddato",
    "value": "2026-10-07"
  }},
  "grounding": [
    {{
      "target": "project_id",
      "quote": "V165460",
      "source": "question"
    }},
    {{
      "target": "selection",
      "quote": "alle installationer",
      "source": "question"
    }},
    {{
      "target": "after.value",
      "quote": "7. oktober",
      "source": "question"
    }}
  ]
}}

3. Ændring af brøndfelt:

{{
"change_type": "manhole_field_change",
"project_id": "V165460",
"manhole_no": "4612031",
"after": {{
"field": "depth_m",
"value": 2.22
}},
"grounding": [
{{
"target": "project_id",
"quote": "V165460",
"source": "question"
}},
{{
"target": "manhole_no",
"quote": "4612031",
"source": "question"
}},
{{
"target": "after.field",
"quote": "dybden",
"source": "question"
}},
{{
"target": "after.value",
"quote": "2,22",
"source": "question"
}}
]
}}

4. Flytning af en installationsopgave til et andet hold:

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
- Brug projektoversigten i systemkonteksten til at identificere
  projekter, når brugeren omtaler dem med projekt-id, projektnavn,
  by eller en anden entydig projektbetegnelse.
- Hvis brugerens projektbetegnelse entydigt matcher ét projekt i
  systemkonteksten, skal det konkrete projekt-id placeres i
  scope.project_ids.
- Projektnavn, by og andre oplysninger, der bruges til at identificere
  projektet, må ikke flyttes over som filtre på den efterfølgende
  dataresource, medmindre feltet faktisk findes direkte på den
  pågældende resource.
- Når et konkret projekt først er identificeret via scope.project_ids,
  skal dataresource normalt hentes inden for dette scope uden at
  gentage projektets navn eller by som filter.
- For resource="project_constraints" skal det relevante projekt
  identificeres via scope.project_ids. Brug ikke projektets by eller
  navn som filter på project_constraints.
- For resource="project_watchdog" skal det relevante projekt
  identificeres via scope.project_ids. Brug ikke projektets by eller
  navn som filter på project_watchdog.
- En besked kan indeholde flere ændringer.
- Hver ændring skal placeres som ét objekt i changes.
- Opfind aldrig projekt-id, installationsnummer eller hold.
- Ved intent="change": Hvis et nødvendigt projekt-id,
  installationsnummer, hold eller opgavetype ikke kan udledes
  sikkert fra spørgsmålet eller samtalekonteksten, brug
  intent="clarification".
- Ved intent="report": Manglende databaseværdier må ikke antages.
  Vælg den relevante dataresource og lad systemet hente dataene.
- Brug intent="change" ved både nye forslag og revisioner af et
  eksisterende scenarie.
- Hvis brugeren ønsker samme installationsændring på samtlige
  installationer i det valgte projekt, skal du ikke opfinde
  installationsnumrene.

- Brug i stedet:
  "selection": {{
    "type": "all"
  }}

- selection.type="all" betyder alle faktiske installationer på det
  valgte projekt. Det efterfølgende systemlag finder de konkrete
  installationer fra projektdata.

- Brug kun installation_id, når brugeren henviser til én konkret
  installation.

- Hvis brugeren siger "alle installationer", må du ikke gætte eller
  generere installation_ids selv.
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
- Ved ændringer: Hvis en nødvendig ændringsværdi ikke kan groundes,
  brug intent="clarification".
- Groundingkravet gælder changes[] og må ikke bruges som grund til
  clarification ved almindelige rapportspørgsmål.
- Du må ikke selv udføre godkendelse, kassering eller
  databasekommandoer.
- Ved intent="scenario_decision" må du kun beskrive brugerens
  beslutning struktureret i scenario_decision.
- Rapporter skal normalt have changes=[].

- data_strategy beskriver, hvordan de nødvendige rapportdata
  skal skaffes.

- Brug data_strategy="fetch", når brugerens spørgsmål handler om
  den aktuelle tilstand i systemet, eller når svaret kræver
  aktuelle projektdata fra databasen.

- Et nyt faktuelt spørgsmål om et projekt, en installation, et hold,
  en plan, fremdrift, restarbejde eller anden systemstatus skal
  normalt bruge:
  data_strategy="fetch"
  sammen med de nødvendige data_requests.

- At det samme projekt eller de samme datatyper findes i den aktive
  samtalekontekst er ikke i sig selv grund nok til at bruge
  data_strategy="reuse_context".

- Brug data_strategy="reuse_context" kun når brugerens spørgsmål
  tydeligt arbejder videre med det allerede viste datasæt, og der
  ikke er behov for at kontrollere den aktuelle systemtilstand igen.

- Typiske tilfælde for data_strategy="reuse_context" er:
  sortering, filtrering, gruppering, opsummering, sammenligning,
  omformatering eller udvælgelse af oplysninger fra det resultat,
  som brugeren lige har fået vist.

- Brug også data_strategy="reuse_context", når brugerens spørgsmål
  indeholder en samtalemæssig reference til det tidligere resultat,
  og referenceobjektet kun kan forstås ud fra previous_answer eller
  det gemte rapportdatasæt.

- Forstå sådanne referencer semantisk.
  Formuleringer som "de", "dem", "disse", "det ovenstående",
  "dem du lige nævnte" eller tilsvarende kan henvise til oplysninger
  i previous_answer. Dette er eksempler på samtalereferencer og ikke
  faste nøgleord eller forretningsregler.

- Hvis brugerens spørgsmål kan forstås fuldt ud uden previous_answer
  og spørger efter den nuværende faktiske tilstand i systemet, skal
  du normalt bruge data_strategy="fetch", også selv om et tidligere
  rapportdatasæt kan indeholde oplysninger om samme emne.

- previous_answer viser, hvad brugeren tidligere har fået
  præsenteret, og må bruges til at forstå samtalemæssige referencer.

- previous_answer og available_data må ikke bruges til at opfinde
  projektfakta eller erstatte en nødvendig ny dataforespørgsel.

- available_data beskriver kun, hvilke typer data der allerede er
  hentet. Det betyder ikke, at dataene nødvendigvis stadig
  repræsenterer den aktuelle systemtilstand.

- Hvis spørgsmålet kræver andre projekter, andre resources,
  andre oplysninger eller en ny kontrol af den aktuelle
  systemtilstand, skal du bruge:
  data_strategy="fetch"
  og de nødvendige data_requests.

- Brug data_strategy="none", når spørgsmålet hverken kræver
  projektdata eller et eksisterende rapportdatasæt.

- Hvis data_strategy="reuse_context", skal data_requests=[].

- Hvis data_strategy="fetch", skal data_requests indeholde de
  resources, Context Builder skal hente.

- Ændringer skal bruge changes og have requires_engine=true.

Regler for struktureret projektoprettelse:

- Brug kun project_creation_action, når intent er
  "project_creation".

- Brug den aktive samtalekontekst til at forstå korte svar
  og opfølgende spørgsmål.

- Ved update skal project_creation_fields indeholde de
  projektoplysninger, brugeren faktisk giver eller korrigerer.

- Ved approve skal brugeren utvetydigt godkende oprettelsen
  af det aktuelle projektudkast.

- Hvis brugeren både godkender og ønsker en rettelse,
  skal handlingen være update. Opret ikke projektet endnu.

- Ved question skal projektudkastet forblive uændret.

- Ved cancel skal projektet ikke oprettes.

- Ved unrelated skal den almindelige hensigt anvendes,
  så et aktivt projektudkast ikke overtager andre samtaler.

- Udtræk ikke oplysninger fra projektets navn som separate
  feltværdier, medmindre brugeren faktisk har angivet dem.

- installation_count er valgfrit. Et uoplyst antal må
  ikke erstattes med et opdigtet antal.

- Returnér ingen feltændringer ved approve, question,
  cancel eller unrelated.

- Interpreteren fortolker kun beskeden. Den må aldrig
  selv oprette eller gemme projektet.

Projektoprettelsens feltstruktur:
- project_id: Projektets V-nummer.
- name: Projektets navn.
- customer: Kunden.
- project_manager: Projektlederen.
- site_manager: Entrepriselederen.
- city: By eller område.
- start_date: Startdato i formatet YYYY-MM-DD.
- installation_count: Antal installationer som positivt heltal.
- preparation_team: Hold til forarbejde, hvis oplyst.

Projektleder og entrepriseleder er selvstændige projektfelter.
De må aldrig samles i notes, summary eller andre felter.

Når brugeren oplyser projektleder, skal værdien placeres i
project_creation_fields.project_manager.

Når brugeren oplyser entrepriseleder, skal værdien placeres i
project_creation_fields.site_manager.

Udtræk alle faktisk oplyste projektfelter i den første besked,
også når flere oplysninger gives i samme sætning.

Brug kun de tilladte feltnavne i project_creation_fields.
Opfind ikke nye felter, og placer ikke oplysninger i notes,
når de har et selvstændigt projektfelt.

Hvis installation_count ikke oplyses, skal feltet udelades.
Det er ikke obligatorisk for projektoprettelse.

Aktiv samtale- og scenariekontekst:
{context_text}

Returnér KUN ét gyldigt JSON-objekt.
Ingen markdown.
Ingen forklaring uden for JSON.

Svarformat:
{{
  "intent": "report | change | scenario_decision | project_creation | general | clarification",
  "confidence": 0.0,
  "summary": "Kort beskrivelse af brugerens hensigt",
  "scope": {{
    "project_ids": [],
    "installation_ids": [],
    "team_ids": []
  }},
  "data_strategy": "fetch | reuse_context | none",
  "data_requests": [],
  "changes": [],
  "scenario_decision": "approve | discard | null",
  "project_creation_action": "update | approve | question | cancel | unrelated | null",
  "project_creation_fields": {{}},
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