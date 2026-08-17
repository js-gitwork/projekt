from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from projektstyring.backend.database.connection import (
    SessionLocal,
)
from projektstyring.backend.db_models import (
    Team as DatabaseTeam,
    WorkCalendar,
)
from projektstyring.backend.team_model import (
    Team,
)


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
                .order_by(
                    DatabaseTeam.name
                )
            )

            if active_only:
                statement = statement.where(
                    DatabaseTeam.active.is_(
                        True
                    )
                )

            database_teams = (
                session.scalars(
                    statement
                ).all()
            )

            return [
                self._to_team_model(
                    database_team
                )
                for database_team
                in database_teams
            ]

    def load_team(
        self,
        team_id: str,
    ) -> Team:
        with SessionLocal() as session:
            statement = (
                select(DatabaseTeam)
                .where(
                    DatabaseTeam.id
                    == team_id
                )
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

            database_team = (
                session.scalar(
                    statement
                )
            )

            if database_team is None:
                raise KeyError(
                    f"Holdet '{team_id}' "
                    "findes ikke."
                )

            return self._to_team_model(
                database_team
            )

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

        capacity_rates: dict[
            str,
            dict[str, float],
        ] = {}

        for rate in (
            database_team.capacity_rates
        ):
            if not rate.active:
                continue

            capacity_rates.setdefault(
                rate.task_type_id,
                {},
            )[
                rate.quantity_type
            ] = float(
                rate.capacity_per_day
            )

        working_days = []

        if database_team.calendar:
            working_days = sorted(
                rule.weekday
                for rule
                in database_team.calendar.rules
                if rule.working
            )

        return Team(
            id=database_team.id,
            name=database_team.name,
            role=database_team.role,
            calendar_id=(
                database_team.calendar_id
                or ""
            ),
            task_types=task_types,
            capacity_rates=capacity_rates,
            working_days=working_days,
            active=database_team.active,
        )