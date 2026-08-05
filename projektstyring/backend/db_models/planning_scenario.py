from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
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


class PlanningScenario(Base):
    """
    Et aktivt planlægningsforløb.

    Et scenarie kan omfatte flere projekter og have mange revisioner.
    Ingen af scenariets forslag ændrer de gældende projektdata, før en
    bestemt revision godkendes og committes.
    """

    __tablename__ = "planning_scenarios"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=create_uuid,
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
        default="Nyt planlægningsscenarie",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        index=True,
    )

    created_by: Mapped[str | None] = mapped_column(
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

    active_revision_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
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

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    projects = relationship(
        "ScenarioProject",
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioProject.sequence",
    )

    revisions = relationship(
        "ScenarioRevision",
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioRevision.revision_number",
    )


class ScenarioProject(Base):
    """
    Kobler et eller flere projekter til et planlægningsscenarie.

    base_project_state gemmer den projekttilstand, som scenariet blev
    beregnet ud fra. Dermed kan systemet senere kontrollere, om det
    virkelige projekt er ændret, før scenariet godkendes.
    """

    __tablename__ = "scenario_projects"

    __table_args__ = (
        UniqueConstraint(
            "scenario_id",
            "project_id",
            name="uq_scenario_projects_scenario_project",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    scenario_id: Mapped[str] = mapped_column(
        ForeignKey(
            "planning_scenarios.id",
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
        default=0,
    )

    base_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "project_snapshots.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    base_project_state: Mapped[dict] = mapped_column(
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

    scenario = relationship(
        "PlanningScenario",
        back_populates="projects",
    )


class ScenarioRevision(Base):
    """
    Én beregnet version af et scenarie.

    En revision er uforanderlig efter oprettelsen. Når brugeren ændrer
    forslaget, oprettes en ny revision i stedet for at overskrive den
    tidligere. Det gør det muligt at gå tilbage til et tidligere forslag.
    """

    __tablename__ = "scenario_revisions"

    __table_args__ = (
        UniqueConstraint(
            "scenario_id",
            "revision_number",
            name="uq_scenario_revisions_scenario_revision",
        ),
        Index(
            "ix_scenario_revisions_scenario_created",
            "scenario_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=create_uuid,
    )

    scenario_id: Mapped[str] = mapped_column(
        ForeignKey(
            "planning_scenarios.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        index=True,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    user_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    ai_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    planner_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="current",
    )

    week_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    week_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    calculated_result: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    conflicts: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    warnings: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    constraints: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
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

    scenario = relationship(
        "PlanningScenario",
        back_populates="revisions",
    )

    activities = relationship(
        "ScenarioActivity",
        back_populates="revision",
        cascade="all, delete-orphan",
        order_by="ScenarioActivity.sequence",
    )

    changes = relationship(
        "ScenarioChange",
        back_populates="revision",
        cascade="all, delete-orphan",
        order_by="ScenarioChange.sequence",
    )


class ScenarioActivity(Base):
    """
    En søgbar aktivitet i én scenarierevision.

    Tabellen indeholder både den gældende og den foreslåede placering.
    Dermed kan samme data bruges til Excel-visning, Gantt, ændringsrapport,
    holdoversigt og live-opdatering.
    """

    __tablename__ = "scenario_activities"

    __table_args__ = (
        UniqueConstraint(
            "revision_id",
            "sequence",
            name="uq_scenario_activities_revision_sequence",
        ),
        Index(
            "ix_scenario_activities_team_dates",
            "team_id",
            "proposed_start",
            "proposed_end",
        ),
        Index(
            "ix_scenario_activities_project_task",
            "project_id",
            "task_type",
        ),
        Index(
            "ix_scenario_activities_revision_change_status",
            "revision_id",
            "change_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    revision_id: Mapped[str] = mapped_column(
        ForeignKey(
            "scenario_revisions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
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
        String(100),
        nullable=True,
        index=True,
    )

    current_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    current_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    proposed_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    proposed_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    change_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="unchanged",
        index=True,
    )

    status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    quantity_data: Mapped[dict] = mapped_column(
        "quantity",
        JSONB,
        nullable=False,
        default=dict,
    )

    notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    lock_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
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

    revision = relationship(
        "ScenarioRevision",
        back_populates="activities",
    )


class ScenarioChange(Base):
    """
    Den strukturerede ændringshistorik for én scenarierevision.

    Denne tabel beskriver brugerens ønskede ændringer. ScenarioActivity
    beskriver derimod resultatet efter planmotorens beregning.
    """

    __tablename__ = "scenario_changes"

    __table_args__ = (
        UniqueConstraint(
            "revision_id",
            "sequence",
            name="uq_scenario_changes_revision_sequence",
        ),
        Index(
            "ix_scenario_changes_target",
            "target_type",
            "target_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    revision_id: Mapped[str] = mapped_column(
        ForeignKey(
            "scenario_revisions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    project_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
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

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="proposed",
        index=True,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
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

    revision = relationship(
        "ScenarioRevision",
        back_populates="changes",
    )
