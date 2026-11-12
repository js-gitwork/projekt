"""add knowledge catalog

Revision ID: 436c3d33ff73
Revises: 50b18c3665c8
Create Date: 2026-11-12 09:46:34.246724

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '436c3d33ff73'
down_revision: Union[str, Sequence[str], None] = '50b18c3665c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Opret udelukkende KnowledgeCatalog."""
    op.create_table('knowledge_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_key', sa.String(length=100), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('schema_fingerprint', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_key')
        )
    op.create_table('knowledge_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('knowledge_key', sa.String(length=255), nullable=False),
        sa.Column('knowledge_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('definition', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('verification_status', sa.String(length=50), nullable=False),
        sa.Column('schema_fingerprint', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['knowledge_sources.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id', 'knowledge_key', name='uq_knowledge_source_key')
        )
    op.create_index('ix_knowledge_source_type_status', 'knowledge_entries', ['source_id', 'knowledge_type', 'verification_status'], unique=False)
    op.create_table('knowledge_evidence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entry_id', sa.Integer(), nullable=False),
        sa.Column('verification_type', sa.String(length=50), nullable=False),
        sa.Column('scope', sa.String(length=255), nullable=False),
        sa.Column('outcome', sa.String(length=50), nullable=False),
        sa.Column('checked_count', sa.Integer(), nullable=True),
        sa.Column('matched_count', sa.Integer(), nullable=True),
        sa.Column('unmatched_count', sa.Integer(), nullable=True),
        sa.Column('verified_by', sa.String(length=100), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['entry_id'], ['knowledge_entries.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
        )
    op.create_index('ix_knowledge_evidence_entry_checked', 'knowledge_evidence', ['entry_id', 'checked_at'], unique=False)


def downgrade() -> None:
    """Fjern udelukkende KnowledgeCatalog."""
    op.drop_index("ix_knowledge_evidence_entry_checked", table_name="knowledge_evidence")
    op.drop_table("knowledge_evidence")
    op.drop_index("ix_knowledge_source_type_status", table_name="knowledge_entries")
    op.drop_table("knowledge_entries")
    op.drop_table("knowledge_sources")
