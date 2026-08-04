from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import (
    Team as DatabaseTeam,
    TeamCapacityRate,
    TeamTaskPermission,
    WorkCalendar,
)
from projektstyring.backend.team_model import Team


WEEKDAY_NAMES = {
    0: "man",
    1: "tir",
    2: "ons",
    3: "tor",
    4: "fre",
    5: "lør",
    6: "søn",
}


class TeamRepository:
    def list_teams(
        self,
        *,
        active_only: bool = True,
    ) -> list[Team]:
        with SessionLocal() as session:
            statement = (
                select(DatabaseTeam)
                .options(
                    selectinload(
                        DatabaseTeam.task_permissions
                    ),
                    selectinload(
                        DatabaseTeam.capacity_rates
                    ),
                    selectinload(
                        DatabaseTeam.calendar
                    ).selectinload(
                        WorkCalendar.rules
                    ),
                )
                .order_by(DatabaseTeam.name)
            )

            if active_only:
                statement = statement.where(
                    DatabaseTeam.active.is_(True)
                )

            database_teams = session.scalars(
                statement
            ).all()

            return [
                self._to_team_model(database_team)
                for database_team in database_teams
            ]

    def load_team(
        self,
        team_id: str,
    ) -> Team:
        with SessionLocal() as session:
            statement = (
                select(DatabaseTeam)
                .where(DatabaseTeam.id == team_id)
                .options(
                    selectinload(
                        DatabaseTeam.task_permissions
                    ),
                    selectinload(
                        DatabaseTeam.capacity_rates
                    ),
                    selectinload(
                        DatabaseTeam.calendar
                    ).selectinload(
                        WorkCalendar.rules
                    ),
                )
            )

            database_team = session.scalar(statement)

            if database_team is None:
                raise KeyError(
                    f"Holdet '{team_id}' findes ikke."
                )

            return self._to_team_model(database_team)

    def load_team_map(
        self,
        *,
        active_only: bool = True,
    ) -> dict[str, Team]:
        teams = self.list_teams(
            active_only=active_only,
        )

        return {
            team.id: team
            for team in teams
        }

    def _to_team_model(
        self,
        database_team: DatabaseTeam,
    ) -> Team:
        task_types = sorted(
            permission.task_type_id
            for permission
            in database_team.task_permissions
            if permission.active
        )

        capacity_per_day = self._resolve_capacity(
            database_team.capacity_rates
        )

        team = Team(
            id=database_team.id,
            name=database_team.name,
            role=database_team.role,
            calendar_id=database_team.calendar_id or "",
            capacity_per_day=capacity_per_day,
            task_types=task_types,
            active=database_team.active,
        )

        working_days = []

        if database_team.calendar:
            working_days = [
                WEEKDAY_NAMES[rule.weekday]
                for rule in sorted(
                    database_team.calendar.rules,
                    key=lambda item: item.weekday,
                )
                if (
                    rule.working
                    and rule.weekday in WEEKDAY_NAMES
                )
            ]

        # Midlertidige kompatibilitetsfelter til den
        # eksisterende planlægningsmotor.
        #
        # MultiScheduleEngine forventer arbejdsdage,
        # mens CapacityEngine stadig bruger de ældre
        # danske attributnavne rolle og kapacitet.
        team.arbejdsdage = working_days
        team.rolle = self._legacy_role(database_team)
        team.kapacitet = capacity_per_day

        return team

    @staticmethod
    def _resolve_capacity(
        capacity_rates: list[TeamCapacityRate],
    ) -> float:
        active_rates = [
            rate
            for rate in capacity_rates
            if rate.active
        ]

        if not active_rates:
            return 0.0

        # Den gamle Team-model understøtter kun én
        # kapacitet pr. hold. Vi vælger derfor den
        # højeste aktive dagskapacitet som midlertidig
        # kompatibilitetsværdi.
        #
        # Det fulde kapacitetsvalg pr. opgavetype
        # flyttes senere til CapacityService.
        return max(
            float(rate.capacity_per_day)
            for rate in active_rates
        )

    @staticmethod
    def _legacy_role(
        database_team: DatabaseTeam,
    ) -> str:
        permissions = {
            permission.task_type_id
            for permission
            in database_team.task_permissions
            if permission.active
        }

        if database_team.role == "dtvk":
            return "stikforberedelse_kontrol"

        if database_team.role == "stik":
            return "langhat"

        if database_team.role == "broend":
            return "brøndrenovering"

        if "hovedledning" in permissions:
            return "hovedledning"

        if "forarbejde" in permissions:
            return "forarbejde"

        if "korthat" in permissions:
            return "korthat"

        return database_team.role
