from typing import List, Dict, Any
from datetime import date

from .models import Aktivitet
from ..core.ai_assistent import ask_mistral


class AIPlannerLayer:

    def __init__(self):
        pass


    # ==================================================
    # 1. ANALYSER PLAN
    # ==================================================
    def analyze_schedule(self, schedule: Dict[date, List[Aktivitet]]):

        summary = self._build_summary(schedule)

        prompt = f"""
Du er en projektplanlægnings-assistent for kloakrenovering.

Analyser denne plan:

{summary}

Find:
1. flaskehalse
2. overbelastede dage
3. urealistisk rækkefølge
4. forbedringsforslag

Svar kort og konkret.
"""

        return ask_mistral(prompt)


    # ==================================================
    # 2. FORESLÅ FORBEDRINGER
    # ==================================================
    def suggest_improvements(self, schedule: Dict[date, List[Aktivitet]]):

        summary = self._build_summary(schedule)

        prompt = f"""
Du er en optimerings-AI for entreprenør-planlægning.

Her er en plan:

{summary}

Foreslå konkrete forbedringer som:
- flytning af aktiviteter mellem dage
- bedre fordeling af hold
- reduktion af flaskehalse

Svar i punktform.
"""

        return ask_mistral(prompt)


    # ==================================================
    # 3. WHAT-IF SIMULATION
    # ==================================================
    def simulate_scenario(self, scenario_text: str, schedule_summary: str):

        prompt = f"""
Du simulerer konsekvenser i et projektplanlægningssystem.

Nuværende plan:
{schedule_summary}

Ændring:
{scenario_text}

Beskriv:
- hvad der bliver påvirket
- hvilke aktiviteter der forsinkes
- hvilke hold der bliver belastet
"""

        return ask_mistral(prompt)


    # ==================================================
    # 4. SUMMARY BUILDER
    # ==================================================
    def _build_summary(self, schedule):

        lines = []

        for day in sorted(schedule.keys()):

            activities = schedule[day]

            line = f"{day}: "

            for a in activities:
                line += f"[{a.type} | {a.installation_id}] "

            lines.append(line)

        return "\n".join(lines)
