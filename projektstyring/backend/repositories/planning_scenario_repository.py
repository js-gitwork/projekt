from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import (
    PlanningScenario,
    ScenarioActivity,
    ScenarioChange,
    ScenarioProject,
    ScenarioRevision,
)


class PlanningScenarioRepository:
    """
    Databaseadgang for planlægningsscenarier.

    Repository-laget:
    - opretter og henter scenarier
    - knytter projekter til scenarier
    - gemmer uforanderlige revisioner
    - gemmer beregnede aktiviteter og ændringer
    - ændrer ikke de virkelige projekter

    Service-laget bestemmer, hvad et scenarie betyder.
    Repository-laget sørger kun for sikker og ensartet lagring.
    """

    # ------------------------------------------------------------
    # Scenarier
    # ------------------------------------------------------------

    def create_scenario(
        self,
        *,
        title: str = "Nyt planlægningsscenarie",
        description: str = "",
        created_by: str | None = None,
        metadata: dict[str, Any] | None = None,
        session: Session | None = None,
    ) -> PlanningScenario:
        """
        Opretter et nyt tomt planlægningsscenarie.

        Hvis en session gives udefra, foretager repository'et ikke commit.
        Det gør det muligt at samle flere handlinger i én transaktion.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            scenario = PlanningScenario(
                title=title.strip() or "Nyt planlægningsscenarie",
                description=description.strip(),
                status="draft",
                created_by=(
                    created_by.strip()
                    if created_by
                    else None
                ),
                metadata_data=deepcopy(metadata or {}),
            )

            db.add(scenario)
            db.flush()

            if owns_session:
                db.commit()
                db.refresh(scenario)

            return scenario

        except Exception:
            if owns_session:
                db.rollback()
            raise

        finally:
            if owns_session:
                db.close()

    def get_scenario(
        self,
        scenario_id: str,
        *,
        include_projects: bool = True,
        include_revisions: bool = False,
        session: Session | None = None,
    ) -> PlanningScenario | None:
        """
        Henter ét scenarie.

        Relationer indlæses eksplicit, så kaldende kode ikke bliver
        afhængig af en åben SQLAlchemy-session.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            statement = select(
                PlanningScenario
            ).where(
                PlanningScenario.id == scenario_id
            )

            options = []

            if include_projects:
                options.append(
                    selectinload(
                        PlanningScenario.projects
                    )
                )

            if include_revisions:
                options.append(
                    selectinload(
                        PlanningScenario.revisions
                    )
                )

            if options:
                statement = statement.options(*options)

            return db.scalar(statement)

        finally:
            if owns_session:
                db.close()

    def require_scenario(
        self,
        scenario_id: str,
        *,
        include_projects: bool = True,
        include_revisions: bool = False,
        session: Session | None = None,
    ) -> PlanningScenario:
        """
        Henter et scenarie eller rejser en tydelig fejl.
        """

        scenario = self.get_scenario(
            scenario_id,
            include_projects=include_projects,
            include_revisions=include_revisions,
            session=session,
        )

        if scenario is None:
            raise FileNotFoundError(
                f"Planlægningsscenariet '{scenario_id}' findes ikke."
            )

        return scenario

    def list_scenarios(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
        session: Session | None = None,
    ) -> list[PlanningScenario]:
        """
        Returnerer scenarier med de senest ændrede først.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            statement = (
                select(PlanningScenario)
                .options(
                    selectinload(
                        PlanningScenario.projects
                    )
                )
                .order_by(
                    PlanningScenario.updated_at.desc()
                )
            )

            if status:
                statement = statement.where(
                    PlanningScenario.status
                    == status
                )

            if limit is not None:
                statement = statement.limit(
                    max(0, int(limit))
                )

            return list(
                db.scalars(statement)
            )

        finally:
            if owns_session:
                db.close()

    def update_scenario_status(
        self,
        scenario_id: str,
        status: str,
        *,
        session: Session | None = None,
    ) -> PlanningScenario:
        """
        Ændrer scenariets overordnede status.

        Tilladte overgange valideres senere i service-laget.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            scenario = db.scalar(
                select(PlanningScenario)
                .where(
                    PlanningScenario.id
                    == scenario_id
                )
                .with_for_update()
            )

            if scenario is None:
                raise FileNotFoundError(
                    f"Planlægningsscenariet "
                    f"'{scenario_id}' findes ikke."
                )

            scenario.status = status.strip()
            db.flush()

            if owns_session:
                db.commit()
                db.refresh(scenario)

            return scenario

        except Exception:
            if owns_session:
                db.rollback()
            raise

        finally:
            if owns_session:
                db.close()

    # ------------------------------------------------------------
    # Projekter i scenariet
    # ------------------------------------------------------------

    def add_project(
        self,
        *,
        scenario_id: str,
        project_id: str,
        base_project_state: dict[str, Any],
        base_snapshot_id: str | None = None,
        sequence: int | None = None,
        metadata: dict[str, Any] | None = None,
        session: Session | None = None,
    ) -> ScenarioProject:
        """
        Knytter et projekt til scenariet.

        Det oprindelige projekt gemmes som base_project_state, så senere
        revisioner altid kan beregnes ud fra det samme udgangspunkt.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            self.require_scenario(
                scenario_id,
                include_projects=False,
                session=db,
            )

            existing = db.scalar(
                select(ScenarioProject).where(
                    ScenarioProject.scenario_id
                    == scenario_id,
                    ScenarioProject.project_id
                    == project_id,
                )
            )

            if existing is not None:
                return existing

            if sequence is None:
                highest_sequence = db.scalar(
                    select(
                        func.max(
                            ScenarioProject.sequence
                        )
                    ).where(
                        ScenarioProject.scenario_id
                        == scenario_id
                    )
                )

                sequence = (
                    int(highest_sequence or 0) + 1
                )

            scenario_project = ScenarioProject(
                scenario_id=scenario_id,
                project_id=project_id,
                sequence=sequence,
                base_snapshot_id=base_snapshot_id,
                base_project_state=deepcopy(
                    base_project_state
                ),
                metadata_data=deepcopy(
                    metadata or {}
                ),
            )

            db.add(scenario_project)
            db.flush()

            if owns_session:
                db.commit()
                db.refresh(scenario_project)

            return scenario_project

        except Exception:
            if owns_session:
                db.rollback()
            raise

        finally:
            if owns_session:
                db.close()

    def get_scenario_projects(
        self,
        scenario_id: str,
        *,
        session: Session | None = None,
    ) -> list[ScenarioProject]:
        """
        Returnerer projekterne i scenariets valgte rækkefølge.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            return list(
                db.scalars(
                    select(ScenarioProject)
                    .where(
                        ScenarioProject.scenario_id
                        == scenario_id
                    )
                    .order_by(
                        ScenarioProject.sequence
                    )
                )
            )

        finally:
            if owns_session:
                db.close()

    def remove_project(
        self,
        *,
        scenario_id: str,
        project_id: str,
        session: Session | None = None,
    ) -> bool:
        """
        Fjerner et projekt fra et kladdescenarie.

        Service-laget skal sikre, at dette kun sker, mens scenariet
        fortsat må redigeres.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            scenario_project = db.scalar(
                select(ScenarioProject).where(
                    ScenarioProject.scenario_id
                    == scenario_id,
                    ScenarioProject.project_id
                    == project_id,
                )
            )

            if scenario_project is None:
                return False

            db.delete(scenario_project)
            db.flush()

            if owns_session:
                db.commit()

            return True

        except Exception:
            if owns_session:
                db.rollback()
            raise

        finally:
            if owns_session:
                db.close()

    # ------------------------------------------------------------
    # Revisioner
    # ------------------------------------------------------------

    def next_revision_number(
        self,
        scenario_id: str,
        *,
        session: Session | None = None,
    ) -> int:
        """
        Finder næste revisionsnummer inden for scenariet.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            highest_revision = db.scalar(
                select(
                    func.max(
                        ScenarioRevision.revision_number
                    )
                ).where(
                    ScenarioRevision.scenario_id
                    == scenario_id
                )
            )

            return int(
                highest_revision or 0
            ) + 1

        finally:
            if owns_session:
                db.close()

    def create_revision(
        self,
        *,
        scenario_id: str,
        reason: str = "",
        user_message: str = "",
        ai_summary: str = "",
        calculated_result: dict[str, Any] | None = None,
        conflicts: list[dict[str, Any]] | None = None,
        warnings: list[dict[str, Any]] | None = None,
        constraints: list[dict[str, Any]] | None = None,
        activities: list[dict[str, Any]] | None = None,
        changes: list[dict[str, Any]] | None = None,
        planner_version: str = "current",
        week_year: int | None = None,
        week_number: int | None = None,
        metadata: dict[str, Any] | None = None,
        session: Session | None = None,
    ) -> ScenarioRevision:
        """
        Opretter en komplet, uforanderlig scenarierevision.

        Revision, aktiviteter og ændringer gemmes i samme transaktion.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            scenario = db.scalar(
                select(PlanningScenario)
                .where(
                    PlanningScenario.id
                    == scenario_id
                )
                .with_for_update()
            )

            if scenario is None:
                raise FileNotFoundError(
                    f"Planlægningsscenariet "
                    f"'{scenario_id}' findes ikke."
                )

            revision_number = (
                self.next_revision_number(
                    scenario_id,
                    session=db,
                )
            )

            revision = ScenarioRevision(
                scenario_id=scenario_id,
                revision_number=revision_number,
                status="draft",
                reason=reason.strip(),
                user_message=user_message.strip(),
                ai_summary=ai_summary.strip(),
                planner_version=(
                    planner_version.strip()
                    or "current"
                ),
                week_year=week_year,
                week_number=week_number,
                calculated_result=deepcopy(
                    calculated_result or {}
                ),
                conflicts=deepcopy(
                    conflicts or []
                ),
                warnings=deepcopy(
                    warnings or []
                ),
                constraints=deepcopy(
                    constraints or []
                ),
                metadata_data=deepcopy(
                    metadata or {}
                ),
            )

            db.add(revision)
            db.flush()

            self._add_revision_activities(
                db,
                revision_id=revision.id,
                activities=activities or [],
            )

            self._add_revision_changes(
                db,
                revision_id=revision.id,
                changes=changes or [],
            )

            scenario.active_revision_number = (
                revision_number
            )

            db.flush()

            if owns_session:
                db.commit()

                revision = self.get_revision(
                    revision.id,
                    session=db,
                )

            return revision

        except Exception:
            if owns_session:
                db.rollback()
            raise

        finally:
            if owns_session:
                db.close()

    def get_revision(
        self,
        revision_id: str,
        *,
        session: Session | None = None,
    ) -> ScenarioRevision | None:
        """
        Henter en revision med aktiviteter og ændringer.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            return db.scalar(
                select(ScenarioRevision)
                .options(
                    selectinload(
                        ScenarioRevision.activities
                    ),
                    selectinload(
                        ScenarioRevision.changes
                    ),
                )
                .where(
                    ScenarioRevision.id
                    == revision_id
                )
            )

        finally:
            if owns_session:
                db.close()

    def get_revision_by_number(
        self,
        *,
        scenario_id: str,
        revision_number: int,
        session: Session | None = None,
    ) -> ScenarioRevision | None:
        """
        Henter en bestemt nummereret revision.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            return db.scalar(
                select(ScenarioRevision)
                .options(
                    selectinload(
                        ScenarioRevision.activities
                    ),
                    selectinload(
                        ScenarioRevision.changes
                    ),
                )
                .where(
                    ScenarioRevision.scenario_id
                    == scenario_id,
                    ScenarioRevision.revision_number
                    == revision_number,
                )
            )

        finally:
            if owns_session:
                db.close()

    def get_active_revision(
        self,
        scenario_id: str,
        *,
        session: Session | None = None,
    ) -> ScenarioRevision | None:
        """
        Returnerer den revision, som scenariet aktuelt peger på.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            scenario = db.scalar(
                select(PlanningScenario).where(
                    PlanningScenario.id
                    == scenario_id
                )
            )

            if (
                scenario is None
                or scenario.active_revision_number
                is None
            ):
                return None

            return self.get_revision_by_number(
                scenario_id=scenario_id,
                revision_number=(
                    scenario.active_revision_number
                ),
                session=db,
            )

        finally:
            if owns_session:
                db.close()

    def list_revisions(
        self,
        scenario_id: str,
        *,
        session: Session | None = None,
    ) -> list[ScenarioRevision]:
        """
        Returnerer hele revisionshistorikken med nyeste først.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            return list(
                db.scalars(
                    select(ScenarioRevision)
                    .where(
                        ScenarioRevision.scenario_id
                        == scenario_id
                    )
                    .order_by(
                        ScenarioRevision
                        .revision_number
                        .desc()
                    )
                )
            )

        finally:
            if owns_session:
                db.close()

    def set_active_revision(
        self,
        *,
        scenario_id: str,
        revision_number: int,
        session: Session | None = None,
    ) -> PlanningScenario:
        """
        Gør en eksisterende revision til scenariets aktive forslag.

        Funktionen ændrer ikke revisionens data.
        """

        owns_session = session is None
        db = session or SessionLocal()

        try:
            scenario = db.scalar(
                select(PlanningScenario)
                .where(
                    PlanningScenario.id
                    == scenario_id
                )
                .with_for_update()
            )

            if scenario is None:
                raise FileNotFoundError(
                    f"Planlægningsscenariet "
                    f"'{scenario_id}' findes ikke."
                )

            revision_exists = db.scalar(
                select(
                    ScenarioRevision.id
                ).where(
                    ScenarioRevision.scenario_id
                    == scenario_id,
                    ScenarioRevision.revision_number
                    == revision_number,
                )
            )

            if revision_exists is None:
                raise FileNotFoundError(
                    f"Revision {revision_number} "
                    f"findes ikke i scenariet."
                )

            scenario.active_revision_number = (
                revision_number
            )

            db.flush()

            if owns_session:
                db.commit()
                db.refresh(scenario)

            return scenario

        except Exception:
            if owns_session:
                db.rollback()
            raise

        finally:
            if owns_session:
                db.close()

    # ------------------------------------------------------------
    # Interne hjælpefunktioner
    # ------------------------------------------------------------

    def _add_revision_activities(
        self,
        session: Session,
        *,
        revision_id: str,
        activities: list[dict[str, Any]],
    ) -> None:
        """
        Gemmer planaktiviteter i deres oprindelige rækkefølge.
        """

        for sequence, activity in enumerate(
            activities,
            start=1,
        ):
            row = ScenarioActivity(
                revision_id=revision_id,
                sequence=sequence,
                project_id=activity["project_id"],
                installation_no=(
                    str(
                        activity.get(
                            "installation_no"
                        )
                    )
                    if activity.get(
                        "installation_no"
                    )
                    is not None
                    else None
                ),
                task_type=str(
                    activity.get("task_type")
                    or ""
                ),
                team_id=activity.get("team_id"),
                current_start=activity.get(
                    "current_start"
                ),
                current_end=activity.get(
                    "current_end"
                ),
                proposed_start=activity.get(
                    "proposed_start"
                ),
                proposed_end=activity.get(
                    "proposed_end"
                ),
                change_status=str(
                    activity.get(
                        "change_status"
                    )
                    or "unchanged"
                ),
                status=activity.get("status"),
                quantity_data=deepcopy(
                    activity.get("quantity")
                    or {}
                ),
                notes=str(
                    activity.get("notes")
                    or ""
                ),
                is_locked=bool(
                    activity.get(
                        "is_locked",
                        False,
                    )
                ),
                lock_reason=str(
                    activity.get(
                        "lock_reason"
                    )
                    or ""
                ),
                metadata_data=deepcopy(
                    activity.get("metadata")
                    or {}
                ),
            )

            session.add(row)

    def _add_revision_changes(
        self,
        session: Session,
        *,
        revision_id: str,
        changes: list[dict[str, Any]],
    ) -> None:
        """
        Gemmer de strukturerede ændringer i deres oprindelige rækkefølge.
        """

        for sequence, change in enumerate(
            changes,
            start=1,
        ):
            row = ScenarioChange(
                revision_id=revision_id,
                sequence=sequence,
                project_id=change.get(
                    "project_id"
                ),
                change_type=str(
                    change.get("change_type")
                    or ""
                ),
                target_type=str(
                    change.get("target_type")
                    or ""
                ),
                target_id=(
                    str(change["target_id"])
                    if change.get("target_id")
                    is not None
                    else None
                ),
                status=str(
                    change.get("status")
                    or "proposed"
                ),
                reason=str(
                    change.get("reason")
                    or ""
                ),
                before_data=deepcopy(
                    change.get("before")
                ),
                after_data=deepcopy(
                    change.get("after")
                ),
                metadata_data=deepcopy(
                    change.get("metadata")
                    or {}
                ),
            )

            session.add(row)
