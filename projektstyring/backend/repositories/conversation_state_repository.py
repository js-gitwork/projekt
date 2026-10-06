from sqlalchemy import select

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.conversation import ConversationState


def list_conversations(
    *,
    user_key: str,
) -> list[ConversationState]:
    with SessionLocal() as session:
        statement = (
            select(ConversationState)
            .where(
                ConversationState.user_key == user_key
            )
            .where(
                ConversationState.status == "active"
            )
            .order_by(
                ConversationState.updated_at.desc(),
                ConversationState.id.desc(),
            )
        )

        return list(
            session.scalars(statement).all()
        )


def get_active_conversation(
    *,
    user_key: str,
    conversation_key: str,
) -> ConversationState | None:
    with SessionLocal() as session:
        statement = (
            select(ConversationState)
            .where(
                ConversationState.user_key == user_key
            )
            .where(
                ConversationState.conversation_key
                == conversation_key
            )
            .where(
                ConversationState.status == "active"
            )
        )

        return session.scalar(statement)


def create_conversation(
    *,
    user_key: str,
    title: str | None = None,
    kind: str = "normal",
    workflow: str = "conversation",
    data: dict | None = None,
) -> ConversationState:
    with SessionLocal() as session:
        state = ConversationState(
            user_key=user_key,
            title=title or "Ny samtale",
            kind=kind,
            workflow=workflow,
            data=data or {},
            status="active",
        )

        session.add(state)
        session.commit()
        session.refresh(state)

        return state

def rename_conversation(
    *,
    user_key: str,
    conversation_key: str,
    title: str,
) -> ConversationState | None:
    with SessionLocal() as session:
        statement = (
            select(ConversationState)
            .where(
                ConversationState.user_key == user_key
            )
            .where(
                ConversationState.conversation_key
                == conversation_key
            )
            .where(
                ConversationState.status == "active"
            )
        )

        state = session.scalar(statement)

        if state is None:
            return None

        state.title = title.strip()[:150]

        session.commit()
        session.refresh(state)

        return state

def save_active_conversation(
    *,
    workflow: str,
    data: dict,
    user_key: str,
    conversation_key: str,
) -> ConversationState:
    with SessionLocal() as session:
        statement = (
            select(ConversationState)
            .where(
                ConversationState.user_key == user_key
            )
            .where(
                ConversationState.conversation_key
                == conversation_key
            )
            .where(
                ConversationState.status == "active"
            )
        )

        state = session.scalar(statement)

        if state is None:
            raise ValueError(
                "Samtalen findes ikke eller tilhører "
                "ikke den aktuelle bruger."
            )

        state.workflow = workflow
        state.data = data

        session.commit()
        session.refresh(state)

        return state


def clear_active_conversation(
    *,
    user_key: str,
    conversation_key: str,
) -> ConversationState | None:
    """
    Rydder workflow-konteksten i en eksisterende fane.

    Samtalen slettes ikke. Fanen kan derfor fortsætte efter
    eksempelvis godkendelse eller kassering af et scenarie.
    """
    with SessionLocal() as session:
        statement = (
            select(ConversationState)
            .where(
                ConversationState.user_key == user_key
            )
            .where(
                ConversationState.conversation_key
                == conversation_key
            )
            .where(
                ConversationState.status == "active"
            )
        )

        state = session.scalar(statement)

        if state is None:
            return None

        state.workflow = "conversation"
        state.data = {}

        session.commit()
        session.refresh(state)

        return state


def delete_conversation(
    *,
    user_key: str,
    conversation_key: str,
) -> bool:
    """
    Sletter en midlertidig Rørbot-samtale.

    Permanente beslutninger, ændringer og snapshots påvirkes ikke.
    """
    with SessionLocal() as session:
        statement = (
            select(ConversationState)
            .where(
                ConversationState.user_key == user_key
            )
            .where(
                ConversationState.conversation_key
                == conversation_key
            )
        )

        state = session.scalar(statement)

        if state is None:
            return False

        session.delete(state)
        session.commit()

        return True
