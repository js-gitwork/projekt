"""add conversation tabs

Revision ID: 29cfa8bbda05
Revises: 7c79169a206b
Create Date: 2026-10-06 07:34:57.208528

"""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "29cfa8bbda05"
down_revision: Union[str, Sequence[str], None] = "7c79169a206b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversation_states",
        sa.Column(
            "conversation_key",
            sa.String(length=36),
            nullable=True,
        ),
    )

    op.add_column(
        "conversation_states",
        sa.Column(
            "title",
            sa.String(length=150),
            nullable=True,
        ),
    )

    op.add_column(
        "conversation_states",
        sa.Column(
            "kind",
            sa.String(length=50),
            nullable=True,
        ),
    )

    connection = op.get_bind()

    conversation_ids = connection.execute(
        sa.text(
            """
            SELECT id
            FROM conversation_states
            ORDER BY id
            """
        )
    ).scalars().all()

    for conversation_id in conversation_ids:
        connection.execute(
            sa.text(
                """
                UPDATE conversation_states
                SET
                    conversation_key = :conversation_key,
                    title = :title,
                    kind = 'normal'
                WHERE id = :conversation_id
                """
            ),
            {
                "conversation_key": str(uuid4()),
                "title": f"Samtale {conversation_id}",
                "conversation_id": conversation_id,
            },
        )

    op.alter_column(
        "conversation_states",
        "conversation_key",
        existing_type=sa.String(length=36),
        nullable=False,
    )

    op.alter_column(
        "conversation_states",
        "title",
        existing_type=sa.String(length=150),
        nullable=False,
    )

    op.alter_column(
        "conversation_states",
        "kind",
        existing_type=sa.String(length=50),
        nullable=False,
    )

    op.create_index(
        op.f(
            "ix_conversation_states_conversation_key"
        ),
        "conversation_states",
        ["conversation_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_conversation_states_conversation_key"
        ),
        table_name="conversation_states",
    )

    op.drop_column(
        "conversation_states",
        "kind",
    )

    op.drop_column(
        "conversation_states",
        "title",
    )

    op.drop_column(
        "conversation_states",
        "conversation_key",
    )
