
"""Backfill manhole connections from stretches and surveys.

Revision ID: a63ce1c44c23
Revises: 00484052e878
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a63ce1c44c23"
down_revision: Union[str, Sequence[str], None] = "00484052e878"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Midlertidig kobling mellem strækende og oprettet tilslutning.
    conn.execute(sa.text("""
        CREATE TEMP TABLE migration_connection_map (
            stretch_id INTEGER NOT NULL,
            endpoint VARCHAR(10) NOT NULL,
            connection_id INTEGER NOT NULL,
            PRIMARY KEY (stretch_id, endpoint),
            UNIQUE (connection_id)
        ) ON COMMIT DROP
    """))

    # Opret én tilslutning for hver ende af hvert stræk.
    # INSERT ... RETURNING kobles entydigt via en midlertidig
    # markør i notes, som fjernes inden transaktionen afsluttes.
    conn.execute(sa.text("""
        INSERT INTO manhole_connections (
            manhole_id,
            connection_type,
            profile,
            dimension_a_mm,
            dimension_b_mm,
            material,
            notes,
            created_at,
            updated_at
        )
        SELECT
            s.bottom_manhole_id,
            'outlet',
            COALESCE(ss.bottom_profile, ''),
            ss.bottom_dimension_a_mm,
            ss.bottom_dimension_b_mm,
            COALESCE(ss.bottom_material, ''),
            '__migration_bottom_' || s.id,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM stretches s
        LEFT JOIN stretch_surveys ss ON ss.stretch_id = s.id
        WHERE s.bottom_connection_id IS NULL
    """))

    conn.execute(sa.text("""
        INSERT INTO manhole_connections (
            manhole_id,
            connection_type,
            profile,
            dimension_a_mm,
            dimension_b_mm,
            material,
            notes,
            created_at,
            updated_at
        )
        SELECT
            s.top_manhole_id,
            'inlet',
            COALESCE(ss.top_profile, ''),
            ss.top_dimension_a_mm,
            ss.top_dimension_b_mm,
            COALESCE(ss.top_material, ''),
            '__migration_top_' || s.id,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM stretches s
        LEFT JOIN stretch_surveys ss ON ss.stretch_id = s.id
        WHERE s.top_connection_id IS NULL
    """))

    # Knyt kun de netop oprettede tilslutninger til strækkene.
    conn.execute(sa.text("""
        INSERT INTO migration_connection_map (
            stretch_id,
            endpoint,
            connection_id
        )
        SELECT
            substring(notes FROM '^__migration_bottom_([0-9]+)$')::INTEGER,
            'bottom',
            id
        FROM manhole_connections
        WHERE notes ~ '^__migration_bottom_[0-9]+$'

        UNION ALL

        SELECT
            substring(notes FROM '^__migration_top_([0-9]+)$')::INTEGER,
            'top',
            id
        FROM manhole_connections
        WHERE notes ~ '^__migration_top_[0-9]+$'
    """))

    conn.execute(sa.text("""
        UPDATE stretches s
        SET bottom_connection_id = m.connection_id
        FROM migration_connection_map m
        WHERE s.id = m.stretch_id
          AND m.endpoint = 'bottom'
          AND s.bottom_connection_id IS NULL
    """))

    conn.execute(sa.text("""
        UPDATE stretches s
        SET top_connection_id = m.connection_id
        FROM migration_connection_map m
        WHERE s.id = m.stretch_id
          AND m.endpoint = 'top'
          AND s.top_connection_id IS NULL
    """))

    # Fjern migrationsmarkørerne.
    conn.execute(sa.text("""
        UPDATE manhole_connections mc
        SET notes = ''
        FROM migration_connection_map m
        WHERE mc.id = m.connection_id
    """))

    # Kontroller at ingen stræk mangler en tilslutning.
    missing = conn.execute(sa.text("""
        SELECT COUNT(*)
        FROM stretches
        WHERE bottom_connection_id IS NULL
           OR top_connection_id IS NULL
    """)).scalar_one()

    if missing:
        raise RuntimeError(
            f"Migration afbrudt: {missing} stræk mangler tilslutninger"
        )

    # Kontroller at tilslutningerne tilhører de rigtige brønde.
    mismatches = conn.execute(sa.text("""
        SELECT COUNT(*)
        FROM stretches s
        JOIN manhole_connections b
          ON b.id = s.bottom_connection_id
        JOIN manhole_connections t
          ON t.id = s.top_connection_id
        WHERE b.manhole_id <> s.bottom_manhole_id
           OR t.manhole_id <> s.top_manhole_id
    """)).scalar_one()

    if mismatches:
        raise RuntimeError(
            f"Migration afbrudt: {mismatches} forkerte brøndrelationer"
        )


def downgrade() -> None:
    raise RuntimeError(
        "Automatisk rollback af datamigrationen er ikke understøttet. "
        "Eksisterende tilslutninger må ikke slettes uden kontrol."
    )
