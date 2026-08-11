from __future__ import annotations

import json
from typing import Any

from core.ai_assistent import ask_mistral
from projektstyring.backend.assistant_tools import run_tool
from projektstyring.backend.conversation_router import route_conversation
from projektstyring.backend.repositories.conversation_state_repository import (
    get_active_conversation,
    save_active_conversation,
)
from projektstyring.backend.roerbot_context import (
    build_context,
    build_interpreter_context,
)
from projektstyring.backend.roerbot_interpreter import interpret_question
from projektstyring.backend.roerbot_reporter import create_report


ACTIVE_CONTEXT_WORKFLOW = "active_context"


def make_json_safe(
    value: Any,
) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )
    )


def save_active_context(
    *,
    context_type: str,
    original_question: str,
    context_data: Any,
    answer: str,
) -> None:
    save_active_conversation(
        workflow=ACTIVE_CONTEXT_WORKFLOW,
        data={
            "context_type": context_type,
            "original_question": original_question,
            "context_data": make_json_safe(
                context_data
            ),
            "answer": answer,
        },
        user_key="default",
    )


def get_active_ai_context(
    active_state: Any,
) -> dict[str, Any] | None:
    """
    Giver AI-interpreteren den aktuelle samtaletilstand.

    AI'en skal kunne se både:
    - et aktivt rapportdatasæt
    - et eventuelt igangværende workflow

    Workflowet får ikke automatisk kontrol over den næste besked.
    AI'en afgør først, om brugerens nye besked faktisk fortsætter
    workflowet eller handler om noget andet.
    """
    if not active_state:
        return None

    data = active_state.data or {}

    if (
        active_state.workflow
        == ACTIVE_CONTEXT_WORKFLOW
    ):
        return {
            "workflow": active_state.workflow,
            "context_type": data.get(
                "context_type"
            ),
            "original_question": data.get(
                "original_question"
            ),
            "previous_answer": data.get(
                "answer"
            ),
            "active_data": data.get(
                "context_data"
            ),
        }

    return {
        "workflow": active_state.workflow,
        "workflow_data": make_json_safe(
            data
        ),
    }


def build_agent_context(
    *,
    question: str,
    active_state: Any,
) -> dict[str, Any]:
    system_context = build_interpreter_context(
        question=question
    )

    return {
        "system": system_context,
        "conversation": get_active_ai_context(
            active_state
        ),
    }


def answer_general_question(
    *,
    question: str,
    conversation_context: dict[str, Any] | None = None,
) -> str:
    prompt = f"""
Du er Roerbot, AI-assistent og sparringspartner i et
projektstyringssystem.

Svar på dansk.

Forstå brugerens besked i sammenhæng med den aktive samtale.
Hvis den aktive samtalekontekst er relevant, må du arbejde
videre med de data, der allerede er hentet.

Du må ikke opfinde konkrete projektdata.
Du må ikke påstå, at en ændring er udført, hvis backend ikke
har udført den.

Aktiv samtalekontekst:
{json.dumps(
    conversation_context or {},
    ensure_ascii=False,
    indent=2,
    default=str,
)}

Brugerens besked:
{question}
"""

    return ask_mistral(
        prompt
    )


def answer_from_existing_context(
    *,
    question: str,
    active_state: Any,
    interpretation: dict[str, Any],
) -> dict[str, str] | None:
    if not active_state:
        return None

    if (
        active_state.workflow
        != ACTIVE_CONTEXT_WORKFLOW
    ):
        return None

    data = active_state.data or {}
    context_data = data.get(
        "context_data"
    )

    if context_data is None:
        return None

    report = create_report(
        question=question,
        interpretation=interpretation,
        context=context_data,
    )

    answer = report["answer"]

    save_active_context(
        context_type=(
            data.get("context_type")
            or "report"
        ),
        original_question=(
            data.get("original_question")
            or question
        ),
        context_data=context_data,
        answer=answer,
    )

    return {
        "answer": answer
    }


def handle_report(
    *,
    question: str,
    interpretation: dict[str, Any],
    active_state: Any,
) -> dict[str, str]:
    data_requests = interpretation.get(
        "data_requests"
    )

    if not isinstance(
        data_requests,
        list,
    ):
        data_requests = []

    if not data_requests:
        continued = answer_from_existing_context(
            question=question,
            active_state=active_state,
            interpretation=interpretation,
        )

        if continued is not None:
            return continued

    context = build_context(
        interpretation
    )

    report = create_report(
        question=question,
        interpretation=interpretation,
        context=context,
    )

    answer = report["answer"]

    save_active_context(
        context_type="report",
        original_question=question,
        context_data=context,
        answer=answer,
    )

    return {
        "answer": answer
    }


def handle_project_creation(
    question: str,
) -> dict[str, str]:
    result = run_tool(
        "analyze_project_creation_request",
        {
            "question": question,
        },
    )

    return {
        "answer": result["answer"]
    }


def handle_change(
    question: str,
) -> dict[str, str]:
    route = route_conversation(
        question
    )

    if route.get("route") == "tool":
        result = run_tool(
            route["tool"],
            route.get(
                "args",
                {},
            ),
        )

        return {
            "answer": result["answer"]
        }

    return {
        "answer": (
            "Jeg forstår, at du ønsker en ændring, "
            "men jeg kan ikke endnu omsætte den sikkert "
            "til et eksisterende ændringsworkflow."
        )
    }


def ask_roerbot(
    question: str,
) -> dict[str, str]:
    """
    Roerbots hovedindgang.

    AI-interpreteren ser ALTID brugerens besked først.

    Et gammelt eller aktivt workflow kan derfor ikke kapre et nyt
    rapport-, analyse- eller samtalespørgsmål. Workflow-routing
    bruges kun efter AI'en har vurderet, at brugerens hensigt er
    en ændring eller projektoprettelse.

    Python håndterer data, beregninger, validering og execution.
    """
    normalized_question = str(
        question or ""
    ).strip()

    if not normalized_question:
        return {
            "answer": "Du skal skrive et spørgsmål."
        }

    active_state = get_active_conversation(
        "default"
    )

    conversation_context = build_agent_context(
        question=normalized_question,
        active_state=active_state,
    )

    interpretation = interpret_question(
        normalized_question,
        conversation_context=conversation_context,
    )

    intent = interpretation.get(
        "intent"
    )

    if intent == "report":
        return handle_report(
            question=normalized_question,
            interpretation=interpretation,
            active_state=active_state,
        )

    if intent == "project_creation":
        return handle_project_creation(
            normalized_question
        )

    if intent == "change":
        return handle_change(
            normalized_question
        )

    if intent == "clarification":
        clarification = (
            interpretation.get(
                "clarification"
            )
            or {}
        )

        clarification_question = str(
            clarification.get(
                "question"
            )
            or ""
        ).strip()

        if clarification_question:
            return {
                "answer": clarification_question
            }

        return {
            "answer": (
                "Jeg mangler lidt mere information "
                "for at kunne fortsætte sikkert."
            )
        }

    return {
        "answer": answer_general_question(
            question=normalized_question,
            conversation_context=(
                get_active_ai_context(
                    active_state
                )
            ),
        )
    }
