from projektstyring.backend.repositories.conversation_state_repository import (
    get_active_conversation,
)


def route_conversation(question, user_key="default"):
    """
    Første routinglag for Roerbot.

    Afgør om beskeden skal fortsætte en aktiv samtale,
    starte en beslutningsdialog, eller sendes videre til normal tool-routing.
    """

    active_state = get_active_conversation(user_key)

    if active_state:
        if active_state.workflow == "project_creation":
            return {
                "route": "tool",
                "tool": "analyze_project_creation_request",
                "args": {
                    "question": question,
                },
            }

        if active_state.workflow == "pending_project_decision":
            return {
                "route": "tool",
                "tool": "continue_pending_project_decision",
                "args": {
                    "question": question,
                },
            }

    pending_decision = detect_project_decision_intent(question)

    if pending_decision:
        return {
            "route": "tool",
            "tool": "start_project_decision_dialog",
            "args": {
                "question": question,
                "intent": pending_decision,
            },
        }

    return {
        "route": "legacy_tool_routing",
        "args": {
            "question": question,
        },
    }


def detect_project_decision_intent(question):
    lower = question.lower()

    if (
        "stik2" in lower
        and ("uge 32" in lower or "inden uge 32" in lower)
        and ("herslev" in lower or "v165460" in lower)
    ):
        return {
            "type": "stik2_before_week_32",
            "requires_decision": True,
            "requires_project": True,
            "description": (
                "Stik2 skal være færdig inden uge 32, "
                "muligvis med workflow-undtagelse."
            ),
        }

    if (
        ("langhat" in lower or "langhatte" in lower)
        and ("før hovedledning" in lower or "inden hovedledning" in lower)
    ):
        return {
            "type": "allow_langhat_before_hovedledning",
            "requires_decision": True,
            "requires_project": True,
            "description": (
                "Langhat ønskes udført før normal hovedledningsafhængighed."
            ),
        }

    return None
