from projektstyring.backend.repositories.conversation_state_repository import (
    clear_active_conversation,
    get_active_conversation,
)


APPROVAL_PREFIXES = (
    "godkendt af ",
    "godkend af ",
    "godkendt ",
)


def looks_like_approval(question):
    lower = question.lower().strip()
    return lower.startswith(APPROVAL_PREFIXES)


def route_conversation(question, user_key="default"):
    """
    Første routinglag for Roerbot.

    Routeren må ikke kende konkrete projekter, hold eller deadlines.
    Den må kun afgøre samtaletilstand og generel beslutningstype.
    """

    active_state = get_active_conversation(user_key)

    if active_state:
        if active_state.workflow == "project_creation":
            return {
                "route": "tool",
                "tool": "analyze_project_creation_request",
                "args": {"question": question},
            }

        if active_state.workflow == "pending_project_decision":
            return {
                "route": "tool",
                "tool": "continue_pending_project_decision",
                "args": {"question": question},
            }

        if active_state.workflow == "pending_solution_choice":
            clear_active_conversation(user_key)

        if active_state.workflow == "pending_decision_approval":
            if looks_like_approval(question):
                return {
                    "route": "tool",
                    "tool": "approve_pending_decision",
                    "args": {"question": question},
                }

            clear_active_conversation(user_key)

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
        "args": {"question": question},
    }


def contains_any(text, phrases):
    return any(phrase in text for phrase in phrases)


def detect_project_decision_intent(question):
    lower = question.lower()

    deadline_words = (
        "færdig inden",
        "færdige inden",
        "klar inden",
        "afsluttet inden",
        "senest",
        "deadline",
        "inden uge",
    )

    workflow_words = (
        "før",
        "inden",
        "førend",
    )

    task_words = (
        "forarbejde",
        "hovedledning",
        "stikforberedelse",
        "stik",
        "kontrol",
        "korthat",
        "langhat",
        "langhatte",
        "brønd",
        "broend",
        "dtvk",
    )

    if contains_any(lower, deadline_words):
        return {
            "type": "deadline_goal",
            "requires_decision": True,
            "requires_project": True,
            "description": "Der ønskes analyse af et deadline-mål.",
        }

    if contains_any(lower, workflow_words) and contains_any(lower, task_words):
        return {
            "type": "workflow_exception",
            "requires_decision": True,
            "requires_project": True,
            "description": "Der ønskes analyse af en mulig workflow-undtagelse.",
        }

    return None