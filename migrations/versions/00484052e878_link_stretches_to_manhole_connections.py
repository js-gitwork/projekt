
"""Link stretches to manhole connections.

Revision ID: 00484052e878
Revises: 0c6c84f535aa
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "00484052e878"
down_revision: Union[str, Sequence[str], None] = "0c6c84f535aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stretches",
        sa.Column(
            "bottom_connection_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "stretches",
        sa.Column(
            "top_connection_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_stretches_bottom_connection_id",
        "stretches",
        ["bottom_connection_id"],
        unique=False,
    )

    op.create_index(
        "ix_stretches_top_connection_id",
        "stretches",
        ["top_connection_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_stretches_bottom_connection_id",
        "stretches",
        "manhole_connections",
        ["bottom_connection_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_foreign_key(
        "fk_stretches_top_connection_id",
        "stretches",
        "manhole_connections",
        ["top_connection_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_stretches_top_connection_id",
        "stretches",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_stretches_bottom_connection_id",
        "stretches",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_stretches_top_connection_id",
        table_name="stretches",
    )

    op.drop_index(
        "ix_stretches_bottom_connection_id",
        table_name="stretches",
    )

    op.drop_column(
        "stretches",
        "top_connection_id",
    )

    op.drop_column(
        "stretches",
        "bottom_connection_id",
    )
