from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from projektstyring.backend.database.connection import (
    SessionLocal,
)
from projektstyring.backend.db_models import (
    CalendarException,
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

            database_teams = list(
                session.scalars(
                    statement
                ).all()
            )

            exceptions = (
                self._load_calendar_exceptions(
                    session,
                    database_teams,
                )
            )

            return [
                self._to_team_model(
                    database_team,
                    calendar_exceptions=(
                        self._exceptions_for_team(
                            database_team,
                            exceptions,
                        )
                    ),
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

            exceptions = (
                self._load_calendar_exceptions(
                    session,
                    [database_team],
                )
            )

            return self._to_team_model(
                database_team,
                calendar_exceptions=(
                    self._exceptions_for_team(
                        database_team,
                        exceptions,
                    )
                ),
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

    def _load_calendar_exceptions(
        self,
        session,
        database_teams: list[DatabaseTeam],
    ) -> list[CalendarException]:
        """
        Henter aktive kalenderundtagelser, som kan
        være relevante for de angivne hold.

        En exception kan være:
        - knyttet direkte til et hold
        - knyttet til holdets arbejdskalender
        """

        if not database_teams:
            return []

        team_ids = [
            team.id
            for team in database_teams
        ]

        calendar_ids = [
            team.calendar_id
            for team in database_teams
            if team.calendar_id
        ]

        conditions = [
            CalendarException.team_id.in_(
                team_ids
            )
        ]

        if calendar_ids:
            conditions.append(
                CalendarException.calendar_id.in_(
                    calendar_ids
                )
            )

        statement = (
            select(CalendarException)
            .where(
                CalendarException.active.is_(
                    True
                ),
                or_(*conditions),
            )
            .order_by(
                CalendarException.date_from,
                CalendarException.date_to,
                CalendarException.id,
            )
        )

        return list(
            session.scalars(
                statement
            ).all()
        )

    def _exceptions_for_team(
        self,
        database_team: DatabaseTeam,
        exceptions: list[CalendarException],
    ) -> list[dict]:
        """
        Finder de exceptions, der faktisk gælder
        for ét bestemt hold.

        En holdspecifik exception gælder kun det
        angivne hold.

        En kalenderexception uden team_id gælder
        alle hold på kalenderen.
        """

        result = []

        for exception in exceptions:
            team_specific = (
                exception.team_id
                == database_team.id
            )

            calendar_wide = (
                exception.team_id is None
                and database_team.calendar_id
                and exception.calendar_id
                == database_team.calendar_id
            )

            if not (
                team_specific
                or calendar_wide
            ):
                continue

            result.append(
                {
                    "id": exception.id,
                    "calendar_id": (
                        exception.calendar_id
                    ),
                    "team_id": (
                        exception.team_id
                    ),
                    "date_from": (
                        exception.date_from
                    ),
                    "date_to": (
                        exception.date_to
                    ),
                    "exception_type": (
                        exception.exception_type
                    ),
                    "working": (
                        exception.working
                    ),
                    "start_time": (
                        exception.start_time
                    ),
                    "end_time": (
                        exception.end_time
                    ),
                    "reason": (
                        exception.reason
                    ),
                    "scope": (
                        "team"
                        if team_specific
                        else "calendar"
                    ),
                }
            )

        return result

    def _to_team_model(
        self,
        database_team: DatabaseTeam,
        *,
        calendar_exceptions: list[
            dict
        ] | None = None,
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
            calendar_exceptions=(
                calendar_exceptions
                or []
            ),
            active=database_team.active,
        )