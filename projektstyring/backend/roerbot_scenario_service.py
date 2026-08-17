from __future__ import annotations

from typing import Any

from projektstyring.backend.roerbot_interpreter import (
    interpret_question,
)
from projektstyring.backend.scenario_change_resolver import (
    resolve_changes,
)
from projektstyring.backend.scenario_change_grounder import (
    ground_changes,
)
from projektstyring.backend.scenario_change_applier import (
    apply_changes,
)
from projektstyring.backend.roerbot_context import (
    build_interpreter_context,
)


class RoerbotScenarioService:
    """
    Samlet facade mellem Roerbot og scenariemotoren.

    Roerbot skal ikke kende de interne detaljer i:
        - Interpreter
        - Grounder
        - Resolver
        - ScenarioChangeApplier

    Servicen kan enten:
        1. modtage brugerens tekst og selv fortolke den
        2. modtage en interpretation, som allerede er lavet

    Den sidste variant bruges af Roerbots hovedindgang, så samme
    brugerbesked ikke sendes til AI-interpreteren to gange.
    """

    def process(
        self,
        *,
        scenario_id: str,
        question: str,
        conversation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Fuld indgang, hvor servicen selv fortolker spørgsmålet.
        """

        interpreter_context = build_interpreter_context(
            question=question,
            scenario_id=scenario_id,
        )

        if conversation_context:
            interpreter_context[
                "conversation"
            ] = conversation_context

        interpretation = interpret_question(
            question,
            conversation_context=interpreter_context,
        )

        return self.process_interpretation(
            scenario_id=scenario_id,
            question=question,
            interpretation=interpretation,
            conversation_context=interpreter_context,
        )

    def process_interpretation(
        self,
        *,
        scenario_id: str,
        question: str,
        interpretation: dict[str, Any],
        conversation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Behandler en allerede udført AI-fortolkning.

        Denne indgang bruges af Roerbots hovedservice, hvor
        interpret_question() allerede er blevet kaldt.

        Dermed undgår vi et ekstra AI-kald.
        """

        intent = str(
            interpretation.get("intent")
            or ""
        ).strip()

        #
        # Brugeren mangler oplysninger
        #
        if intent == "clarification":
            return {
                "status": "clarification",
                "interpretation": interpretation,
                "answer": (
                    interpretation.get(
                        "clarification"
                    )
                    or {}
                ).get(
                    "question",
                    "Jeg mangler nogle oplysninger.",
                ),
            }

        #
        # Rapportspørgsmål
        #
        if intent == "report":
            return {
                "status": "report",
                "interpretation": interpretation,
            }

        #
        # Almindelige spørgsmål
        #
        if intent == "general":
            return {
                "status": "general",
                "interpretation": interpretation,
            }

        #
        # Projektoprettelse
        #
        if intent == "project_creation":
            return {
                "status": "project_creation",
                "interpretation": interpretation,
            }

        #
        # Scenarieændringer
        #
        if intent == "change":
            try:
                grounded_changes = ground_changes(
                    question=question,
                    changes=interpretation.get(
                        "changes",
                        [],
                    ),
                    conversation_context=(
                        conversation_context
                    ),
                )

                resolved_changes = resolve_changes(
                    grounded_changes
                )

            except Exception as error:
                return {
                    "status": "validation_error",
                    "interpretation": interpretation,
                    "answer": str(error),
                }

            try:
                scenario = apply_changes(
                    scenario_id=scenario_id,
                    user_message=question,
                    reason=str(
                        interpretation.get(
                            "summary"
                        )
                        or ""
                    ),
                    changes=resolved_changes,
                )

            except Exception as error:
                return {
                    "status": "engine_error",
                    "interpretation": interpretation,
                    "answer": str(error),
                }

            return {
                "status": "scenario_updated",
                "interpretation": interpretation,
                "scenario": scenario,
            }

        return {
            "status": "unknown",
            "interpretation": interpretation,
        }


roerbot_scenario_service = (
    RoerbotScenarioService()
)