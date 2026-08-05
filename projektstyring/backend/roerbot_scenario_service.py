from __future__ import annotations

from typing import Any

from projektstyring.backend.roerbot_interpreter import (
    interpret_question,
)
from projektstyring.backend.scenario_change_resolver import (
    resolve_changes,
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

    Roerbot skal ikke kende til:
        - Interpreter
        - Resolver
        - ScenarioChangeApplier

    Den afleverer blot brugerens tekst.

    Denne service afgør derefter,
    hvordan teksten skal behandles.
    """

    def process(
        self,
        *,
        scenario_id: str,
        question: str,
        conversation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

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

        intent = interpretation["intent"]

        #
        # Brugeren mangler oplysninger
        #
        if intent == "clarification":
            return {
                "status": "clarification",
                "interpretation": interpretation,
                "answer": (
                    interpretation["clarification"]
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
        # Planændringer
        #
        if intent == "change":

            try:

                resolved_changes = resolve_changes(
                    interpretation["changes"]
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
                    reason=interpretation["summary"],
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
