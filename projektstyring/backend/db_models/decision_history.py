from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from projektstyring.backend.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_uuid() -> str:
    return str(uuid4())


class Decision(Base):
    """
    En beslutning repræsenterer det samlede, strukturerede ændringssæt,
    som Roerbot eller en bruger har simuleret og eventuelt godkendt.

    AI-genereret fri tekst må aldrig skrives direkte til projektdata.
    Den skal først omsættes til change_set.
    """

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    decision_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="simulated",
        index=True,
    )

    trigger: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manual",
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    requested_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    approved_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    committed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Det validerede ændringssæt, som executor skal anvende.
    change_set: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Resultatet fra simulationen, før beslutningen blev godkendt.
    simulation_result: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Eksempelvis brugerens oprindelige formulering,
    # Roerbots forklaring og tekniske sporingsoplysninger.
    metadata_data: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    changes = relationship(
        "DecisionChange",
        back_populates="decision",
        cascade="all, delete-orphan",
        order_by="DecisionChange.sequence",
    )

    snapshots = relationship(
        "ProjectSnapshot",
        back_populates="decision",
    )


class DecisionChange(Base):
    """
    En søgbar og sammenlignelig registrering af hver enkelt ændring
    i en samlet beslutning.

    Hele change_set gemmes samtidig på Decision, men disse rækker gør
    historiske analyser mulige uden at gennemgå JSONB manuelt.
    """

    __tablename__ = "decision_changes"

    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "sequence",
            name="uq_decision_changes_decision_sequence",
        ),
        Index(
            "ix_decision_changes_target",
            "target_type",
            "target_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    decision_id: Mapped[int] = mapped_column(
        ForeignKey(
            "decisions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    change_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    target_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    target_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    before_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    after_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    metadata_data: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    decision = relationship(
        "Decision",
        back_populates="changes",
    )


class ProjectSnapshot(Base):
    """
    En permanent projektversion.

    Snapshot gemmer både projektets tilstand og den faktisk beregnede
    plan på oprettelsestidspunktet. Dermed ændres historiske planer
    ikke, hvis planlægningsmotoren senere bliver ændret.
    """

    __tablename__ = "project_snapshots"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version",
            name="uq_project_snapshots_project_version",
        ),
        Index(
            "ix_project_snapshots_project_created",
            "project_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=create_uuid,
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    decision_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "decisions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    snapshot_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manual",
        index=True,
    )

    # before, after eller standalone.
    phase: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="standalone",
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    approved_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    # Komplet serialiseret projekttilstand.
    project_state: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    # Projektspecifikke regler gemmes særskilt, så de er nemme
    # at sammenligne og gendanne.
    project_rules: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    # Den faktiske beregnede plan på snapshot-tidspunktet.
    calculated_plan: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    planner_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="current",
    )

    metadata_data: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    decision = relationship(
        "Decision",
        back_populates="snapshots",
    )

    plan_activities = relationship(
        "SnapshotPlanActivity",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="SnapshotPlanActivity.sequence",
    )


class SnapshotPlanActivity(Base):
    """
    Søgbar kopi af planens aktiviteter.

    calculated_plan på ProjectSnapshot bevarer hele planen som JSONB.
    Denne tabel gør tværgående rapporter og sammenligninger effektive.
    """

    __tablename__ = "snapshot_plan_activities"

    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "sequence",
            name="uq_snapshot_plan_activities_snapshot_sequence",
        ),
        Index(
            "ix_snapshot_plan_activities_team_dates",
            "team_id",
            "start_date",
            "end_date",
        ),
        Index(
            "ix_snapshot_plan_activities_project_task",
            "project_id",
            "task_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey(
            "project_snapshots.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    installation_no: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    task_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    team_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "teams.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="planned",
    )

    quantities: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    metadata_data: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    snapshot = relationship(
        "ProjectSnapshot",
        back_populates="plan_activities",
    )
