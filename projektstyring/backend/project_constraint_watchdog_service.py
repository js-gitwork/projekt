from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from projektstyring.backend.project_constraint_status_service import (
    ProjectConstraintStatusService,
)
from projektstyring.backend.project_planner import (
    generate_plan_for_project,
)
from projektstyring.backend.project_repository import (
    ProjectRepository,
)
from projektstyring.backend.remaining_work_service import (
    RemainingWorkService,
)
from projektstyring.backend.repositories.project_constraint_repository import (
    ProjectConstraintRepository,
)


class ProjectConstraintWatchdogService:
    """
    Deterministisk, read-only watchdog for projektets faktuelle constraints.

    Servicen ændrer ingen data og foretager ingen planlægning.

    Datakilder:
    - projektets registrerede hoveddatoer
    - eksisterende beregnet plan, når den findes
    - faktisk kendt restarbejde
    - åbne afvigelser
    - rådighedstilladelser
    - projektd deadlines

    Vigtige semantiske regler:
    - ukendt status er ikke det samme som restarbejde
    - kun kendt restarbejde med remaining > 0 regnes som restarbejde
    - åbne afvigelser regnes som dokumenteret uløst arbejde
    - tilladelse uden slutdato betragtes ikke som dokumenteret gyldig
    - tilladelsens slutdato er inklusiv
    """

    PERMIT_APPLICATION_WARNING_DAYS = 14
    DEADLINE_WARNING_DAYS = 14

    def __init__(
        self,
        project_repository: ProjectRepository | None = None,
        constraint_repository: ProjectConstraintRepository | None = None,
        remaining_work_service: RemainingWorkService | None = None,
        constraint_status_service: ProjectConstraintStatusService | None = None,
    ) -> None:
        self.project_repository = (
            project_repository
            if project_repository is not None
            else ProjectRepository()
        )

        self.constraint_repository = (
            constraint_repository
            if constraint_repository is not None
            else ProjectConstraintRepository()
        )

        self.remaining_work_service = (
            remaining_work_service
            if remaining_work_service is not None
            else RemainingWorkService()
        )

        self.constraint_status_service = (
            constraint_status_service
            if constraint_status_service is not None
            else ProjectConstraintStatusService()
        )

    def build_project_watchdog(
        self,
        project_id: str,
        *,
        as_of_date: date | None = None,
    ) -> dict[str, Any]:
        """
        Bygger watchdog-resultatet ud fra projektets aktuelle live-data.

        Denne metode er adapteren mellem repositories/services og den
        deterministiske evaluator.

        Selve forretningsreglerne ligger i evaluate_project_state(),
        så de senere kan genbruges på et scenaries låste projektstate
        uden at læse projektet igen fra live-databasen.
        """

        evaluation_date = as_of_date or date.today()

        project = self.project_repository.load_project(
            project_id
        )

        factual_inputs = (
            self.load_project_factual_inputs(
                project_id
            )
        )

        remaining_work = factual_inputs[
            "remaining_work"
        ]

        constraints = factual_inputs[
            "constraints"
        ]

        plan_activities = self._load_plan_activities(
            project
        )

        return self.evaluate_project_state(
            project_id=project_id,
            project=project,
            constraints=constraints,
            remaining_work=remaining_work,
            activities=plan_activities,
            as_of_date=evaluation_date,
        )

    def load_project_factual_inputs(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        """
        Henter de faktuelle input, som ikke ændres af selve
        planlægningsscenariet.

        Disse data kan snapshots sammen med en scenarierevision,
        så det senere kan dokumenteres, hvilke fakta evalueringen
        byggede på.
        """

        remaining_work = (
            self.remaining_work_service
            .build_project_remaining_work(
                project_id
            )
        )

        constraints = (
            self.constraint_repository
            .list_for_project(
                project_id
            )
        )

        return {
            "remaining_work": remaining_work,
            "constraints": constraints,
        }

    def evaluate_project_state(
        self,
        *,
        project_id: str,
        project: dict[str, Any],
        constraints: list[dict[str, Any]],
        remaining_work: dict[str, Any],
        activities: list[Any],
        as_of_date: date,
    ) -> dict[str, Any]:
        """
        Evaluerer én allerede fastlagt projekttilstand.

        Metoden foretager ingen repository-opslag og genererer ikke
        selv en plan. Alle nødvendige input leveres af kaldende kode.

        Dermed kan præcis de samme deterministiske regler bruges på:

        - projektets aktuelle live-state
        - en scenarierevisions before-state
        - en scenarierevisions after-state

        Evaluatoren ændrer ingen data.
        """

        permits = [
            constraint
            for constraint in constraints
            if constraint.get(
                "constraint_type"
            )
            == "availability_permit"
        ]

        deadlines = [
            constraint
            for constraint in constraints
            if constraint.get(
                "constraint_type"
            )
            == "project_deadline"
        ]

        known_remaining_work = (
            self._collect_known_remaining_work(
                remaining_work
            )
        )

        open_deviations = list(
            remaining_work.get(
                "open_deviations",
                [],
            )
        )

        warnings: list[
            dict[str, Any]
        ] = []

        warnings.extend(
            self._check_upcoming_main_work_permits(
                project=project,
                permits=permits,
                as_of_date=as_of_date,
            )
        )

        warnings.extend(
            self._check_plan_against_permits(
                permits=permits,
                activities=activities,
            )
        )

        warnings.extend(
            self._check_remaining_work_against_permits(
                permits=permits,
                known_remaining_work=(
                    known_remaining_work
                ),
                open_deviations=open_deviations,
                as_of_date=as_of_date,
            )
        )

        warnings.extend(
            self._check_project_deadlines(
                deadlines=deadlines,
                activities=activities,
                known_remaining_work=(
                    known_remaining_work
                ),
                open_deviations=open_deviations,
                as_of_date=as_of_date,
            )
        )

        warnings.sort(
            key=self._warning_sort_key
        )

        return {
            "project_id": project_id,
            "as_of_date": as_of_date,
            "known_remaining_work_count": len(
                known_remaining_work
            ),
            "open_deviation_count": len(
                open_deviations
            ),
            "warning_count": len(
                warnings
            ),
            "warnings": warnings,
        }
    def _load_plan_activities(
        self,
        project: dict[str, Any],
    ) -> list[Any]:
        """
        Genbruger den eksisterende planmotor.

        En tom plan er gyldig input til watchdoggen og betyder ikke,
        at projektet nødvendigvis er færdigt.
        """

        schedule_result = generate_plan_for_project(project)

        return list(
            schedule_result.activities
        )

    def _collect_known_remaining_work(
        self,
        remaining_work: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Finder kun dokumenteret restarbejde.

        known=False regnes ikke som restarbejde.
        relevant_as_remaining_work=False ignoreres.
        """

        result: list[dict[str, Any]] = []

        for installation in remaining_work.get(
            "installations",
            [],
        ):
            installation_no = str(
                installation.get("installation_id", "")
            ).strip()

            tasks = installation.get("tasks", {})

            if not isinstance(tasks, dict):
                continue

            for task_type, task in tasks.items():
                if not isinstance(task, dict):
                    continue

                if (
                    task.get("relevant_as_remaining_work")
                    is False
                ):
                    continue

                if task.get("known") is not True:
                    continue

                remaining = task.get("remaining")

                if not self._has_positive_remaining(
                    remaining
                ):
                    continue

                result.append(
                    {
                        "installation_no": installation_no,
                        "task_type": task_type,
                        "remaining": remaining,
                    }
                )

        return result

    def _check_upcoming_main_work_permits(
        self,
        *,
        project: dict[str, Any],
        permits: list[dict[str, Any]],
        as_of_date: date,
    ) -> list[dict[str, Any]]:
        """
        Hvis hovedledning starter inden for 14 dage, skal der findes
        en dokumenteret tilladelse, som dækker både installationen
        og den planlagte startdato.
        """

        warnings: list[dict[str, Any]] = []

        warning_limit = (
            as_of_date
            + timedelta(
                days=self.PERMIT_APPLICATION_WARNING_DAYS
            )
        )

        for installation in project.get(
            "installations",
            [],
        ):
            if not installation.get("active", True):
                continue

            installation_no = str(
                installation.get("id", "")
            ).strip()

            start_date = self._date_or_none(
                installation.get("hoveddato")
            )

            if start_date is None:
                continue

            if start_date < as_of_date:
                continue

            if start_date > warning_limit:
                continue

            relevant_permits = (
                self._permits_for_installation(
                    permits,
                    installation_no,
                )
            )

            if self._has_confirmed_permit_for_date(
                relevant_permits,
                target_date=start_date,
            ):
                continue

            unknown_end_permits = [
                permit
                for permit in relevant_permits
                if self._permit_could_start_by_date(
                    permit,
                    start_date,
                )
                and self._date_or_none(
                    permit.get("end_date")
                )
                is None
            ]

            if unknown_end_permits:
                warnings.append(
                    {
                        "warning_type": (
                            "upcoming_main_work_permit_validity_unknown"
                        ),
                        "severity": "warning",
                        "constraint_type": (
                            "availability_permit"
                        ),
                        "installation_no": installation_no,
                        "planned_start_date": start_date,
                        "days_until_start": (
                            start_date - as_of_date
                        ).days,
                        "permit_references": [
                            permit.get("reference")
                            for permit in unknown_end_permits
                        ],
                        "message": (
                            "Hovedledning på installation "
                            f"{installation_no} er planlagt "
                            f"til {start_date.isoformat()}, "
                            "men den registrerede "
                            "rådighedstilladelse mangler "
                            "slutdato. Det kan derfor ikke "
                            "dokumenteres, at tilladelsen "
                            "dækker opstarten."
                        ),
                    }
                )

                continue

            warnings.append(
                {
                    "warning_type": (
                        "missing_upcoming_permit"
                    ),
                    "severity": "warning",
                    "constraint_type": (
                        "availability_permit"
                    ),
                    "installation_no": installation_no,
                    "planned_start_date": start_date,
                    "days_until_start": (
                        start_date - as_of_date
                    ).days,
                    "message": (
                        "Hovedledning på installation "
                        f"{installation_no} er planlagt "
                        f"til {start_date.isoformat()}, "
                        "men der findes ingen dokumenteret "
                        "rådighedstilladelse, som dækker "
                        "installationen og startdatoen. "
                        "Tilladelsen skal afklares før "
                        "opstart."
                    ),
                }
            )

        return warnings

    def _check_plan_against_permits(
        self,
        *,
        permits: list[dict[str, Any]],
        activities: list[Any],
    ) -> list[dict[str, Any]]:
        """
        Hvis planmotoren giver aktiviteter, sammenholdes disse
        direkte med tilladelserne.

        Denne kontrol er supplerende. Watchdoggen må ikke være
        afhængig af, at planmotoren returnerer aktiviteter.
        """

        warnings: list[dict[str, Any]] = []

        for permit in permits:
            end_date = self._date_or_none(
                permit.get("end_date")
            )

            if end_date is None:
                continue

            covered_installations = (
                self._permit_installation_nos(
                    permit
                )
            )

            relevant_activities = [
                activity
                for activity in activities
                if self._permit_covers_installation(
                    covered_installations,
                    str(
                        activity.installation_id
                    ),
                )
            ]

            latest_end = max(
                (
                    activity.slut_dato
                    for activity in relevant_activities
                    if activity.slut_dato is not None
                ),
                default=None,
            )

            if latest_end is None:
                continue

            if latest_end <= end_date:
                continue

            warnings.append(
                {
                    "warning_type": (
                        "permit_expires_before_plan_end"
                    ),
                    "severity": "warning",
                    "constraint_type": (
                        "availability_permit"
                    ),
                    "reference": permit.get(
                        "reference"
                    ),
                    "permit_end_date": end_date,
                    "planned_end_date": latest_end,
                    "installation_nos": sorted(
                        covered_installations
                    ),
                    "message": (
                        "Rådighedstilladelsen "
                        f"{permit.get('reference') or ''} "
                        f"udløber {end_date.isoformat()}, "
                        "men den beregnede plan har arbejde "
                        "under tilladelsen frem til "
                        f"{latest_end.isoformat()}. "
                        "Der skal tages stilling til "
                        "forlængelse."
                    ),
                }
            )

        return warnings

    def _check_remaining_work_against_permits(
        self,
        *,
        permits: list[dict[str, Any]],
        known_remaining_work: list[dict[str, Any]],
        open_deviations: list[dict[str, Any]],
        as_of_date: date,
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []

        for permit in permits:
            covered_installations = (
                self._permit_installation_nos(
                    permit
                )
            )

            relevant_remaining = [
                item
                for item in known_remaining_work
                if self._permit_covers_installation(
                    covered_installations,
                    item["installation_no"],
                )
            ]

            relevant_deviations = [
                deviation
                for deviation in open_deviations
                if self._permit_covers_installation(
                    covered_installations,
                    str(
                        deviation.get(
                            "installation_no",
                            "",
                        )
                    ).strip(),
                )
            ]

            if (
                not relevant_remaining
                and not relevant_deviations
            ):
                continue

            status_result = (
                self.constraint_status_service
                .evaluate(
                    permit,
                    as_of_date=as_of_date,
                )
            )

            status = status_result.get("status")

            if status == "valid":
                continue

            if status == "future":
                warnings.append(
                    self._build_remaining_work_permit_warning(
                        warning_type=(
                            "remaining_work_before_permit_start"
                        ),
                        permit=permit,
                        known_remaining_work=relevant_remaining,
                        open_deviations=relevant_deviations,
                        as_of_date=as_of_date,
                        message=(
                            "Der findes dokumenteret "
                            "restarbejde under "
                            f"rådighedstilladelse "
                            f"{permit.get('reference') or ''}, "
                            "men tilladelsens gyldighedsperiode "
                            "er endnu ikke startet."
                        ),
                    )
                )

                continue

            if status == "expires_today":
                warnings.append(
                    self._build_remaining_work_permit_warning(
                        warning_type=(
                            "permit_expires_today_with_remaining_work"
                        ),
                        permit=permit,
                        known_remaining_work=relevant_remaining,
                        open_deviations=relevant_deviations,
                        as_of_date=as_of_date,
                        message=(
                            "Rådighedstilladelsen "
                            f"{permit.get('reference') or ''} "
                            f"udløber i dag "
                            f"{as_of_date.isoformat()}, "
                            "og der er stadig dokumenteret "
                            "restarbejde eller åbne "
                            "afvigelser på installationer, "
                            "som tilladelsen dækker. "
                            "Behov for forlængelse skal "
                            "afklares."
                        ),
                    )
                )

                continue

            if status == "expired":
                warnings.append(
                    self._build_remaining_work_permit_warning(
                        warning_type=(
                            "expired_permit_with_remaining_work"
                        ),
                        permit=permit,
                        known_remaining_work=relevant_remaining,
                        open_deviations=relevant_deviations,
                        as_of_date=as_of_date,
                        message=(
                            "Rådighedstilladelsen "
                            f"{permit.get('reference') or ''} "
                            "er udløbet, men der er stadig "
                            "dokumenteret restarbejde eller "
                            "åbne afvigelser på installationer, "
                            "som tilladelsen dækker."
                        ),
                    )
                )

                continue

            if status == "end_date_unknown":
                warnings.append(
                    self._build_remaining_work_permit_warning(
                        warning_type=(
                            "permit_end_unknown_with_remaining_work"
                        ),
                        permit=permit,
                        known_remaining_work=relevant_remaining,
                        open_deviations=relevant_deviations,
                        as_of_date=as_of_date,
                        message=(
                            "Rådighedstilladelsen "
                            f"{permit.get('reference') or ''} "
                            "har ingen registreret slutdato, "
                            "og der er dokumenteret "
                            "restarbejde eller åbne "
                            "afvigelser på installationer, "
                            "som tilladelsen dækker. "
                            "Tilladelsens aktuelle gyldighed "
                            "kan derfor ikke dokumenteres."
                        ),
                    )
                )

        return warnings

    def _build_remaining_work_permit_warning(
        self,
        *,
        warning_type: str,
        permit: dict[str, Any],
        known_remaining_work: list[dict[str, Any]],
        open_deviations: list[dict[str, Any]],
        as_of_date: date,
        message: str,
    ) -> dict[str, Any]:
        affected_installations = {
            item["installation_no"]
            for item in known_remaining_work
        }

        affected_installations.update(
            str(
                deviation.get(
                    "installation_no",
                    "",
                )
            ).strip()
            for deviation in open_deviations
            if str(
                deviation.get(
                    "installation_no",
                    "",
                )
            ).strip()
        )

        return {
            "warning_type": warning_type,
            "severity": "warning",
            "constraint_type": (
                "availability_permit"
            ),
            "reference": permit.get("reference"),
            "permit_start_date": self._date_or_none(
                permit.get("start_date")
            ),
            "permit_end_date": self._date_or_none(
                permit.get("end_date")
            ),
            "as_of_date": as_of_date,
            "installation_nos": sorted(
                affected_installations
            ),
            "remaining_tasks": [
                {
                    "installation_no": (
                        item["installation_no"]
                    ),
                    "task_type": item["task_type"],
                    "remaining": item["remaining"],
                }
                for item in known_remaining_work
            ],
            "open_deviation_numbers": [
                deviation.get("deviation_number")
                for deviation in open_deviations
            ],
            "message": message,
        }

    def _check_project_deadlines(
        self,
        *,
        deadlines: list[dict[str, Any]],
        activities: list[Any],
        known_remaining_work: list[dict[str, Any]],
        open_deviations: list[dict[str, Any]],
        as_of_date: date,
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []

        latest_plan_end = max(
            (
                activity.slut_dato
                for activity in activities
                if activity.slut_dato is not None
            ),
            default=None,
        )

        has_unfinished_work = bool(
            known_remaining_work
            or open_deviations
        )

        for deadline in deadlines:
            deadline_date = self._constraint_date(
                deadline
            )

            if deadline_date is None:
                continue

            if (
                latest_plan_end is not None
                and latest_plan_end > deadline_date
            ):
                warnings.append(
                    {
                        "warning_type": (
                            "plan_exceeds_project_deadline"
                        ),
                        "severity": "warning",
                        "constraint_type": (
                            "project_deadline"
                        ),
                        "reference": deadline.get(
                            "reference"
                        ),
                        "deadline": deadline_date,
                        "planned_end_date": (
                            latest_plan_end
                        ),
                        "message": (
                            "Den beregnede plan slutter "
                            f"{latest_plan_end.isoformat()}, "
                            "men projektets deadline er "
                            f"{deadline_date.isoformat()}."
                        ),
                    }
                )

            if not has_unfinished_work:
                continue

            days_until_deadline = (
                deadline_date - as_of_date
            ).days

            if days_until_deadline < 0:
                warning_type = (
                    "unfinished_work_after_project_deadline"
                )

                message = (
                    "Projektets deadline "
                    f"{deadline_date.isoformat()} "
                    "er overskredet, og projektet har "
                    "stadig dokumenteret restarbejde "
                    "eller åbne afvigelser."
                )

            elif days_until_deadline <= (
                self.DEADLINE_WARNING_DAYS
            ):
                warning_type = (
                    "unfinished_work_near_project_deadline"
                )

                message = (
                    "Projektet har dokumenteret "
                    "restarbejde eller åbne afvigelser "
                    "og deadline "
                    f"{deadline_date.isoformat()} "
                    f"om {days_until_deadline} dage."
                )

            else:
                continue

            warnings.append(
                {
                    "warning_type": warning_type,
                    "severity": "warning",
                    "constraint_type": (
                        "project_deadline"
                    ),
                    "reference": deadline.get(
                        "reference"
                    ),
                    "deadline": deadline_date,
                    "days_until_deadline": (
                        days_until_deadline
                    ),
                    "remaining_task_count": len(
                        known_remaining_work
                    ),
                    "open_deviation_count": len(
                        open_deviations
                    ),
                    "open_deviation_numbers": [
                        deviation.get(
                            "deviation_number"
                        )
                        for deviation
                        in open_deviations
                    ],
                    "message": message,
                }
            )

        return warnings

    def _permits_for_installation(
        self,
        permits: list[dict[str, Any]],
        installation_no: str,
    ) -> list[dict[str, Any]]:
        return [
            permit
            for permit in permits
            if self._permit_covers_installation(
                self._permit_installation_nos(
                    permit
                ),
                installation_no,
            )
        ]

    @staticmethod
    def _permit_installation_nos(
        permit: dict[str, Any],
    ) -> set[str]:
        metadata = permit.get("metadata")

        if not isinstance(metadata, dict):
            metadata = {}

        return {
            str(value).strip()
            for value in metadata.get(
                "installation_nos",
                [],
            )
            if str(value).strip()
        }

    @staticmethod
    def _permit_covers_installation(
        covered_installations: set[str],
        installation_no: str,
    ) -> bool:
        """
        Tom coverage betyder projektomfattende constraint.

        Når C5 faktisk har installationsnumre, anvendes de
        direkte og deterministisk.
        """

        if not covered_installations:
            return True

        return (
            str(installation_no).strip()
            in covered_installations
        )

    def _has_confirmed_permit_for_date(
        self,
        permits: list[dict[str, Any]],
        *,
        target_date: date,
    ) -> bool:
        for permit in permits:
            start_date = self._date_or_none(
                permit.get("start_date")
            )

            end_date = self._date_or_none(
                permit.get("end_date")
            )

            if (
                start_date is not None
                and target_date < start_date
            ):
                continue

            if end_date is None:
                continue

            if target_date <= end_date:
                return True

        return False

    def _permit_could_start_by_date(
        self,
        permit: dict[str, Any],
        target_date: date,
    ) -> bool:
        start_date = self._date_or_none(
            permit.get("start_date")
        )

        if start_date is None:
            return True

        return start_date <= target_date

    def _constraint_date(
        self,
        constraint: dict[str, Any],
    ) -> date | None:
        end_date = self._date_or_none(
            constraint.get("end_date")
        )

        if end_date is not None:
            return end_date

        return self._date_or_none(
            constraint.get("start_date")
        )

    @staticmethod
    def _has_positive_remaining(
        value: Any,
    ) -> bool:
        if value is None:
            return False

        try:
            return float(value) > 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _date_or_none(
        value: date | str | None,
    ) -> date | None:
        if value in (None, ""):
            return None

        if isinstance(value, date):
            return value

        return date.fromisoformat(
            str(value)
        )

    @staticmethod
    def _warning_sort_key(
        warning: dict[str, Any],
    ) -> tuple:
        warning_date = (
            warning.get("planned_start_date")
            or warning.get("permit_end_date")
            or warning.get("deadline")
            or date.max
        )

        return (
            warning_date,
            str(
                warning.get(
                    "warning_type",
                    "",
                )
            ),
            str(
                warning.get(
                    "reference",
                    "",
                )
            ),
            str(
                warning.get(
                    "installation_no",
                    "",
                )
            ),
        )