"""
Roerbot Reporter
================

Lader AI analysere og formidle data, som Context Builder allerede har hentet.

Reporterens opgave er:
- at forstå sammenhænge i de leverede data
- at filtrere og sammenligne inden for datasættet
- at formulere rapporter, svar og anbefalinger
- at gøre usikkerheder tydelige

Reporteren må ikke:
- opfinde projektdata
- hente yderligere data på egen hånd
- ændre databasen
- tilsidesætte resultater fra plan- eller beslutningsmotorer
"""

from __future__ import annotations

import json
from typing import Any

from core.ai_assistent import ask_mistral


def build_report_prompt(
    *,
    question: str,
    interpretation: dict[str, Any],
    context: dict[str, Any],
) -> str:
    """
    Bygger en rapportprompt med tydelig adskillelse mellem
    brugerens spørgsmål, AI-fortolkningen og systemets data.
    """

    return f"""
Du er Roerbot, projektassistent for strømpeforingsprojekter.

Du skal besvare brugerens spørgsmål ud fra de vedlagte systemdata.

Vigtige regler:
- Brug kun værdier, som findes i systemdata.
- Opfind aldrig projekt-id, hold, installationer, datoer eller mængder.
- Hvis nødvendige data mangler, skal du sige præcist hvad der mangler.
- Filtrér, gruppér og sammenlign data efter brugerens hensigt.
- Gengiv ikke hele datasættet, hvis et kortere svar er tilstrækkeligt.
- Forklar relevante mønstre og afvigelser.
- Skeln mellem fakta fra data og dine egne vurderinger.
- En vurdering skal begrundes med konkrete data.
- Du må ikke skrive, at noget er ændret eller gemt.
- Resultater fra planmotoren skal behandles som systemets beregnede resultat.
- Svar på dansk, medmindre fortolkningen udtrykkeligt kræver andet.

Brugerens oprindelige spørgsmål:
{question}

Fortolket hensigt:
{json.dumps(
    interpretation,
    indent=2,
    ensure_ascii=False,
    default=str,
)}

Systemdata:
{json.dumps(
    context,
    indent=2,
    ensure_ascii=False,
    default=str,
)}

Skriv nu det bedst mulige svar til brugeren.
""".strip()


def create_report(
    *,
    question: str,
    interpretation: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """
    Genererer en fri, databaseret rapport.

    Funktionen returnerer samme ydre struktur som den eksisterende
    ask_roerbot-funktion.
    """

    prompt = build_report_prompt(
        question=question,
        interpretation=interpretation,
        context=context,
    )

    answer = ask_mistral(prompt)

    return {
        "answer": str(answer or "").strip(),
        "interpretation": interpretation,
        "context": context,
    }
