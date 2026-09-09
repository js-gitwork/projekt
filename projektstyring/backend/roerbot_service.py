from __future__ import annotations

import json
from typing import Any

from core.ai_assistent import ask_mistral
from projektstyring.backend.project_creation_service import (
    PROJECT_CREATION_WORKFLOW,
    analyze_project_creation,
    handle_project_creation_message,
    is_confirmation,
)
from projektstyring.backend.repositories.conversation_state_repository import (
    clear_active_conversation,
    get_active_conversation,
    save_active_conversation,
)
from projektstyring.backend.planning_scenario_service import (
    PlanningScenarioService,
)
from projektstyring.backend.roerbot_scenario_service import (
    roerbot_scenario_service,
)
from projektstyring.backend.roerbot_context import (
    build_context,
    build_interpreter_context,
)
from projektstyring.backend.roerbot_interpreter import interpret_question
from projektstyring.backend.roerbot_reporter import create_report
from projektstyring.backend.decision_service import (
    approve_scenario_revision,
)


ACTIVE_CONTEXT_WORKFLOW = "active_context"

def build_report_context_summary(
    interpretation: dict[str, Any],
) -> dict[str, Any]:
    """
    Bygger en lille beskrivelse af et gemt rapportdatasæt.

    Interpreteren får kun denne beskrivelse.
    Det fulde context_data forbliver i conversation state
    og gives kun til Reporter, når data skal genbruges.
    """
    scope = interpretation.get("scope")

    if not isinstance(scope, dict):
        scope = {}

    data_requests = interpretation.get(
        "data_requests"
    )

    if not isinstance(data_requests, list):
        data_requests = []

    resources: list[str] = []

    for request in data_requests:
        if not isinstance(request, dict):
            continue

        resource = str(
            request.get("resource") or ""
        ).strip()

        if (
            resource
            and resource not in resources
        ):
            resources.append(resource)

    return {
        "project_ids": list(
            scope.get("project_ids") or []
        ),
        "installation_ids": list(
            scope.get("installation_ids") or []
        ),
        "team_ids": list(
            scope.get("team_ids") or []
        ),
        "resources": resources,
        "analysis_type": str(
            (
                interpretation.get("analysis")
                or {}
            ).get("type")
            or ""
        ),
        "response_format": str(
            (
                interpretation.get("response")
                or {}
            ).get("format")
            or ""
        ),
    }

planning_scenario_service = (
    PlanningScenarioService()
)

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
    context_summary: dict[str, Any] | None = None,
) -> None:
    save_active_conversation(
        workflow=ACTIVE_CONTEXT_WORKFLOW,
        data={
            "context_type": context_type,
            "original_question": original_question,
            "context_data": make_json_safe(
                context_data
            ),
            "context_summary": make_json_safe(
                context_summary or {}
            ),
            "answer": answer,
        },
        user_key="default",
    )


def get_active_ai_context(
    active_state: Any,
) -> dict[str, Any] | None:
    """
    Giver Interpreteren en kompakt beskrivelse af den
    aktuelle samtaletilstand.

    Det fulde rapportdatasæt sendes bevidst IKKE til
    Interpreteren. Det gemmes i conversation state og
    kan senere genbruges direkte af Reporter.
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
            "available_data": data.get(
                "context_summary"
            )
            or {},
            "has_reusable_context": (
                data.get("context_data")
                is not None
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
    """
    Besvarer et opfølgende rapportspørgsmål ud fra det
    allerede gemte rapportdatasæt.

    Interpreteren har på forhånd vurderet, at spørgsmålet
    kan besvares uden at hente nye systemdata.
    """

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
        previous_answer=str(
            data.get("answer")
            or ""
        ),
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
        context_summary=(
            data.get("context_summary")
            or {}
        ),
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
    """
    Behandler rapportspørgsmål ud fra Interpreterens
    eksplicitte datastrategi.

    fetch:
        Hent nye data gennem Context Builder.

    reuse_context:
        Genbrug det fulde datasæt fra den aktive samtale.

    none:
        Rapporten kræver ingen nye data. Hvis der findes et
        genbrugeligt rapportdatasæt, kan det bruges som
        samtalekontekst.
    """

    data_strategy = str(
        interpretation.get("data_strategy")
        or ""
    ).strip()

    data_requests = interpretation.get(
        "data_requests"
    )

    if not isinstance(
        data_requests,
        list,
    ):
        data_requests = []

    if data_strategy == "reuse_context":
        continued = answer_from_existing_context(
            question=question,
            active_state=active_state,
            interpretation=interpretation,
        )

        if continued is not None:
            return continued

        return {
            "answer": (
                "Jeg kan se, at spørgsmålet henviser til "
                "et tidligere rapportresultat, men det "
                "tilhørende datasæt er ikke længere "
                "tilgængeligt."
            )
        }

    if data_strategy == "none":
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
        context_summary=(
            build_report_context_summary(
                interpretation
            )
        ),
    )

    return {
        "answer": answer
    }

def handle_project_creation(
    question: str,
) -> dict[str, str]:
    result = handle_project_creation_message(
        question,
        user_key="default",
    )

    return {
        "answer": result["answer"]
    }

def handle_scenario_change(
    *,
    question: str,
    interpretation: dict[str, Any],
    active_state: Any,
    conversation_context: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Behandler en struktureret ændring gennem den fælles
    scenariemotor.

    Et eksisterende aktivt scenario genbruges.
    Hvis samtalen endnu ikke har et scenario, oprettes et nyt
    for de projekter, som interpreterens scope indeholder.

    Den virkelige projektdatabase ændres ikke her.
    """

    active_data = {}

    if active_state is not None:
        active_data = dict(
            active_state.data or {}
        )

    scenario_id = str(
        active_data.get("scenario_id")
        or ""
    ).strip()

    if scenario_id:
        try:
            existing_scenario = (
                planning_scenario_service.get_scenario(
                    scenario_id
                )
            )

            if existing_scenario.get("status") in {
                "committed",
                "cancelled",
           }:
                scenario_id = ""

        except FileNotFoundError:
            scenario_id = ""

    scope = (
        interpretation.get("scope")
        or {}
    )
    project_ids = [
        str(project_id).strip()
        for project_id in scope.get(
            "project_ids",
            [],
        )
        if str(project_id).strip()
    ]

    if not scenario_id:
        if not project_ids:
            return {
                "answer": (
                    "Jeg kan se, at du ønsker en ændring, "
                    "men jeg kan ikke sikkert afgøre, "
                    "hvilket projekt scenariet skal tilhøre."
                )
            }

        scenario = (
            planning_scenario_service.create_scenario(
                project_ids=project_ids,
                title="Rørbot-scenarie",
                description=(
                    "Scenarie oprettet fra Rørbot-samtalen."
                ),
                created_by="roerbot",
                user_message=question,
                metadata={
                    "source": "roerbot",
                },
            )
        )

        scenario_id = str(
            scenario["scenario_id"]
        )

    result = (
        roerbot_scenario_service.process_interpretation(
            scenario_id=scenario_id,
            question=question,
            interpretation=interpretation,
            conversation_context=conversation_context,
        )
    )

    status = result.get("status")

    if status in {
        "validation_error",
        "engine_error",
        "clarification",
    }:
        return {
            "answer": str(
                result.get("answer")
                or "Ændringen kunne ikke behandles sikkert."
            )
        }

    if status != "scenario_updated":
        return {
            "answer": (
                "Ændringen kunne ikke omsættes "
                "til et scenarie."
            )
        }

    scenario = result["scenario"]

    active_revision = (
        scenario.get("active_revision")
        or {}
    )

    changes = (
        active_revision.get("changes")
        or []
    )

    # Bevar den eksisterende samtaletilstand,
    # men knyt det aktive scenario til den.
    merged_data = {
        **active_data,
        "scenario_id": scenario_id,
    }

    workflow = (
        active_state.workflow
        if active_state is not None
        else "scenario"
    )

    save_active_conversation(
        workflow=workflow,
        data=merged_data,
        user_key="default",
    )

    if len(changes) == 1:
        change = changes[0]

        before = (
            change.get("before")
            or {}
        )

        after = (
            change.get("after")
            or {}
        )

        field = str(
            after.get("field")
            or before.get("field")
            or ""
        )

        before_value = before.get(
            "value"
        )

        after_value = after.get(
            "value"
        )

        target_type = str(
            change.get("target_type")
            or ""
        )

        target_id = str(
            change.get("target_id")
            or ""
        )

        if target_type == "manhole":
            target_text = (
                f"brønd {target_id}"
            )
        elif target_type == "installation":
            target_text = (
                f"installation {target_id}"
            )
        else:
            target_text = (
                target_id
                or target_type
                or "det valgte objekt"
            )

        return {
            "answer": (
                f"Jeg har oprettet et forslag i scenariet.\n\n"
                f"Ændring: {target_text}\n"
                f"Felt: {field}\n"
                f"Fra: {before_value}\n"
                f"Til: {after_value}\n\n"
                "Ændringen er ikke gemt i de gældende data endnu.\n\n"
                "Skal jeg godkende og gennemføre ændringen?"
            )
        }

    return {
        "answer": (
            f"Jeg har lagt {len(changes)} foreslåede ændringer "
            "ind i scenariet.\n\n"
            "De gældende data er ikke ændret endnu.\n\n"
            "Skal jeg godkende og gennemføre ændringerne?"
        )
    }

def handle_scenario_approval(
    *,
    question: str,
    active_state: Any,
) -> dict[str, str] | None:
    """
    Godkender et aktivt Rørbot-scenarie, hvis brugerens besked
    tydeligt er en bekræftelse.
    """

    if active_state is None:
        return None

    data = dict(
        active_state.data or {}
    )

    scenario_id = str(
        data.get("scenario_id")
        or ""
    ).strip()

    if not scenario_id:
        return None

    normalized = str(
        question or ""
    ).strip().casefold()

    approvals = {
        "ja",
        "ja tak",
        "godkend",
        "godkend ændringen",
        "gennemfør",
        "gennemfør ændringen",
        "ok",
        "okay",
    }

    if normalized not in approvals:
        return None

    result = approve_scenario_revision(
        scenario_id=scenario_id,
        approved_by="Jacob",
    )

    if result.get("ok"):
        clear_active_conversation(
            "default"
        )

    return {
        "answer": str(
            result.get("answer")
            or "Scenariet er behandlet."
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

    if (
        active_state is not None
        and active_state.workflow
        == PROJECT_CREATION_WORKFLOW
    ):
        creation_data = dict(
            active_state.data or {}
        )

        creation_analysis = (
            analyze_project_creation(
                creation_data
            )
        )

        if (
            creation_analysis.get("complete")
            and is_confirmation(
                normalized_question
            )
        ):
            return handle_project_creation(
                normalized_question
            )

    approval_result = handle_scenario_approval(
        question=normalized_question,
        active_state=active_state,
    )

    if approval_result is not None:
        return approval_result

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
        return handle_scenario_change(
            question=normalized_question,
            interpretation=interpretation,
            active_state=active_state,
            conversation_context=conversation_context,
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
