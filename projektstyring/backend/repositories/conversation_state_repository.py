from sqlalchemy import select
from sqlalchemy.orm import Session

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.conversation import ConversationState


DEFAULT_USER_KEY = "default"


def _get_active_conversations(
    session: Session,
    user_key: str,
) -> list[ConversationState]:
    statement = (
        select(ConversationState)
        .where(ConversationState.user_key == user_key)
        .where(ConversationState.status == "active")
        .order_by(
            ConversationState.updated_at.desc(),
            ConversationState.id.desc(),
        )
    )

    return list(session.scalars(statement).all())


def _get_active_conversation(
    session: Session,
    user_key: str,
) -> ConversationState | None:
    active_states = _get_active_conversations(
        session=session,
        user_key=user_key,
    )

    if not active_states:
        return None

    return active_states[0]


def get_active_conversation(
    user_key: str = DEFAULT_USER_KEY,
) -> ConversationState | None:
    with SessionLocal() as session:
        return _get_active_conversation(
            session=session,
            user_key=user_key,
        )


def save_active_conversation(
    workflow: str,
    data: dict,
    user_key: str = DEFAULT_USER_KEY,
) -> ConversationState:
    with SessionLocal() as session:
        active_states = _get_active_conversations(
            session=session,
            user_key=user_key,
        )

        if active_states:
            state = active_states[0]

            state.workflow = workflow
            state.data = data
            state.status = "active"

            # Hvis der ved tidligere kørsel er blevet oprettet flere
            # aktive samtaler for samme bruger, lukkes de ældre.
            for stale_state in active_states[1:]:
                stale_state.status = "closed"

        else:
            state = ConversationState(
                user_key=user_key,
                workflow=workflow,
                data=data,
                status="active",
            )
            session.add(state)

        session.commit()
        session.refresh(state)

        return state


def clear_active_conversation(
    user_key: str = DEFAULT_USER_KEY,
) -> ConversationState | None:
    with SessionLocal() as session:
        active_states = _get_active_conversations(
            session=session,
            user_key=user_key,
        )

        if not active_states:
            return None

        latest_state = active_states[0]

        for state in active_states:
            state.status = "closed"

        session.commit()
        session.refresh(latest_state)

        return latest_state