
"""Add manhole connections.

Revision ID: 0c6c84f535aa
Revises: b818d5aa88bf
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0c6c84f535aa"
down_revision: Union[str, Sequence[str], None] = "b818d5aa88bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "manhole_connections",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "manhole_id",
            sa.Integer(),
            sa.ForeignKey(
                "manholes.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "connection_type",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "profile",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "dimension_a_mm",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "dimension_b_mm",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "material",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "connection_type IN ('inlet', 'outlet')",
            name="ck_manhole_connections_type",
        ),
        sa.CheckConstraint(
            "dimension_a_mm IS NULL OR dimension_a_mm > 0",
            name="ck_manhole_connections_dimension_a",
        ),
        sa.CheckConstraint(
            "dimension_b_mm IS NULL OR dimension_b_mm > 0",
            name="ck_manhole_connections_dimension_b",
        ),
    )

    op.create_index(
        "ix_manhole_connections_manhole_id",
        "manhole_connections",
        ["manhole_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_manhole_connections_manhole_id",
        table_name="manhole_connections",
    )

    op.drop_table("manhole_connections")
