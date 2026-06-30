from sqlalchemy import select

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.conversation import ConversationState


DEFAULT_USER_KEY = "default"


def get_active_conversation(user_key=DEFAULT_USER_KEY):
    with SessionLocal() as session:
        statement = (
            select(ConversationState)
            .where(ConversationState.user_key == user_key)
            .where(ConversationState.status == "active")
            .order_by(ConversationState.updated_at.desc())
        )

        return session.scalars(statement).first()


def save_active_conversation(
    workflow,
    data,
    user_key=DEFAULT_USER_KEY,
):
    with SessionLocal() as session:
        existing = get_active_conversation(user_key)

        if existing:
            existing.workflow = workflow
            existing.data = data
            session.merge(existing)
            session.commit()
            return existing

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


def clear_active_conversation(user_key=DEFAULT_USER_KEY):
    with SessionLocal() as session:
        existing = get_active_conversation(user_key)

        if not existing:
            return None

        existing.status = "closed"
        session.merge(existing)
        session.commit()

        return existing