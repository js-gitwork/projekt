from __future__ import annotations

from typing import Any

from projektstyring.backend.production_status_service import (
    ProductionStatusService,
)
from projektstyring.backend.project_repository import (
    ProjectRepository,
)
from projektstyring.backend.repositories.production_group_repository import (
    ProductionGroupRepository,
)


class RemainingWorkService:
    """
    Samler planlagt arbejde og faktisk produktionsstatus.

    Servicen ændrer ingen data.

    Grundprincipper:

    - stik er ikke det samme som langhat
    - langhat og korthat er selvstændige arbejdsarter
    - brøndskud og punktreparationer er selvstændige arbejdsarter
    - produktionsgrupper beskriver hvilke arbejder,
      der operationelt udføres sammen
    - arbejdsarter lægges ikke sammen til et kunstigt antal stik
    - antal unikke åbne stik angives kun, når datagrundlaget
      gør det muligt at beregne det sikkert
    - manglende produktionsstatus gættes aldrig
    """

    def __init__(
        self,
        project_repository: ProjectRepository | None = None,
        production_status_service: ProductionStatusService | None = None,
        production_group_repository: ProductionGroupRepository | None = None,
    ) -> None:
        self.project_repository = (
            project_repository
            if project_repository is not None
            else ProjectRepository()
        )

        self.production_status_service = (
            production_status_service
            if production_status_service is not None
            else ProductionStatusService()
        )

        self.production_group_repository = (
            production_group_repository
            if production_group_repository is not None
            else ProductionGroupRepository()
        )

    def build_project_remaining_work(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        project = self.project_repository.load_project(
            project_id
        )

        production_report = (
            self.production_status_service
            .build_project_report(
                project_id
            )
        )

        production_by_installation = {
            str(item.get("installation_no")): item
            for item in production_report.get(
                "installations",
                [],
            )
        }

        installations = []

        for installation in project.get(
            "installations",
            [],
        ):
            if not installation.get(
                "active",
                True,
            ):
                continue

            installation_id = str(
                installation["id"]
            )

            production = (
                production_by_installation.get(
                    installation_id,
                    {},
                )
            )

            installations.append(
                self._build_installation_remaining_work(
                    installation=installation,
                    production=production,
                )
            )

        production_groups = (
            self.production_group_repository
            .list_groups()
        )

        production_group_status = (
            self._build_project_production_group_status(
                installations=installations,
                production_groups=production_groups,
            )
        )

        return {
            "project_id": project_id,
            "production_groups": production_groups,
            "production_group_status": (
                production_group_status
            ),
            "installations": installations,
        }

    def _build_installation_remaining_work(
        self,
        *,
        installation: dict[str, Any],
        production: dict[str, Any],
    ) -> dict[str, Any]:
        installation_id = str(
            installation["id"]
        )

        planned_stik = int(
            installation.get("active_stik")
            or installation.get("expected_stik")
            or 0
        )

        planned_broende = int(
            installation.get("broende")
            or 0
        )

        langhat_status = (
            production.get("langhat")
            or {}
        )

        korthat_status = (
            production.get("korthat")
            or {}
        )

        broendskud_status = (
            production.get("broendskud")
            or {}
        )

        pkt_rep_status = (
            production.get("pkt_rep")
            or {}
        )

        missing_main_stretches = (
            production.get(
                "missing_main_stretches"
            )
            or []
        )

        tasks = {
            "hovedledning": (
                self._build_main_task(
                    missing_stretches=(
                        missing_main_stretches
                    ),
                )
            ),
            "stikforberedelse": (
                self._unknown_task(
                    planned=planned_stik,
                    quantity_type="stik",
                    task_type="stikforberedelse",
                )
            ),
            "stik": (
                self._build_stik_task(
                    planned=planned_stik,
                )
            ),
            "langhat": (
                self._build_fraction_work(
                    status=langhat_status,
                    quantity_type="stik",
                    work_type="langhat",
                )
            ),
            "kontrol": (
                self._unknown_task(
                    planned=planned_stik,
                    quantity_type="stik",
                    task_type="kontrol",
                )
            ),
            "korthat": (
                self._build_fraction_work(
                    status=korthat_status,
                    quantity_type="stik",
                    work_type="korthat",
                )
            ),
            "broendskud": (
                self._build_fraction_work(
                    status=broendskud_status,
                    quantity_type="stk",
                    work_type="broendskud",
                )
            ),
            "pkt_rep": (
                self._build_fraction_work(
                    status=pkt_rep_status,
                    quantity_type="stk",
                    work_type="pkt_rep",
                )
            ),
            "broend": (
                self._unknown_task(
                    planned=planned_broende,
                    quantity_type="broende",
                    task_type="broend",
                )
            ),
            "dtvk": (
                self._unknown_task(
                    planned=(
                        1
                        if planned_stik > 0
                        else 0
                    ),
                    quantity_type="activity",
                    task_type="dtvk",
                )
            ),
        }

        self._apply_derived_completion_rules(
            tasks
        )

        return {
            "installation_id": installation_id,
            "tasks": tasks,
        }
    @staticmethod
    def _apply_derived_completion_rules(
        tasks: dict[str, dict[str, Any]],
    ) -> None:
        """
        Anvender domæneregler, hvor en senere dokumenteret
        aktivitet beviser, at nødvendige foregående aktiviteter
        allerede må være udført.

        Korthat kan kun være udført efter det nødvendige
        stikarbejde. Derfor betragtes følgende planlægningsopgaver
        som færdige, når korthat er kendt færdig:

        - stikforberedelse
        - stik
        - kontrol

        Reglen ændrer ikke den registrerede produktionsstatus.
        Den markerer alene planlægningsopgavernes status som
        afledt af en efterfølgende dokumenteret aktivitet.
        """

        korthat = tasks.get(
            "korthat"
        )

        if not isinstance(
            korthat,
            dict,
        ):
            return

        if not (
            korthat.get("known") is True
            and korthat.get("complete") is True
        ):
            return

        for task_type in (
            "stikforberedelse",
            "stik",
            "kontrol",
        ):
            task = tasks.get(
                task_type
            )

            if not isinstance(
                task,
                dict,
            ):
                continue

            planned = task.get(
                "planned"
            )

            task["known"] = True
            task["completed"] = planned
            task["remaining"] = 0
            task["complete"] = True
            task["status_source"] = "derived"
            task["derived_from"] = "korthat"

    def _build_project_production_group_status(
        self,
        *,
        installations: list[dict[str, Any]],
        production_groups: list[dict[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for group in production_groups:
            group_id = str(
                group["id"]
            )

            work_types = [
                str(work_type)
                for work_type
                in group.get(
                    "work_types",
                    [],
                )
            ]

            members: dict[str, Any] = {}

            for work_type in work_types:
                members[work_type] = (
                    self._summarize_work_type(
                        installations=installations,
                        work_type=work_type,
                    )
                )

            group_status = {
                "id": group_id,
                "name": group.get("name"),
                "task_types": list(
                    group.get(
                        "task_types",
                        [],
                    )
                ),
                "work_types": work_types,
                "members": members,
            }

            if group_id == "stikarbejde":
                group_status[
                    "open_unique_stik"
                ] = None
                group_status[
                    "open_unique_stik_known"
                ] = False

            result[group_id] = (
                group_status
            )

        return result

    @staticmethod
    def _summarize_work_type(
        *,
        installations: list[dict[str, Any]],
        work_type: str,
    ) -> dict[str, Any]:
        planned = 0
        completed = 0
        remaining = 0
        known_installations = 0
        unknown_installations = 0

        for installation in installations:
            task = (
                installation.get(
                    "tasks",
                    {},
                ).get(
                    work_type
                )
            )

            if not isinstance(
                task,
                dict,
            ):
                continue

            if not task.get(
                "known",
                False,
            ):
                unknown_installations += 1
                continue

            known_installations += 1

            planned += int(
                task.get("planned")
                or 0
            )

            completed += int(
                task.get("completed")
                or 0
            )

            remaining += int(
                task.get("remaining")
                or 0
            )

        return {
            "work_type": work_type,
            "known": (
                known_installations > 0
            ),
            "complete": (
                known_installations > 0
                and remaining == 0
            ),
            "planned": planned,
            "completed": completed,
            "remaining": remaining,
            "known_installations": (
                known_installations
            ),
            "unknown_installations": (
                unknown_installations
            ),
        }

    def _build_stik_task(
        self,
        *,
        planned: int,
    ) -> dict[str, Any]:
        groups = (
            self.production_group_repository
            .find_groups_for_task_type(
                "stik"
            )
        )

        return {
            "kind": "task_type",
            "task_type": "stik",
            "known": False,
            "planned": planned,
            "completed": None,
            "remaining": None,
            "complete": None,
            "quantity_type": "stik",
            "open_unique": None,
            "open_unique_known": False,
            "production_groups": [
                group["id"]
                for group in groups
            ],
        }

    def _build_fraction_work(
        self,
        *,
        status: dict[str, Any],
        quantity_type: str,
        work_type: str,
    ) -> dict[str, Any]:
        total = int(
            status.get("total")
            or 0
        )

        completed = int(
            status.get("completed")
            or 0
        )

        missing = int(
            status.get("missing")
            or 0
        )

        has_status = (
            total > 0
            or completed > 0
            or missing > 0
        )

        groups = (
            self.production_group_repository
            .find_groups_for_work_type(
                work_type
            )
        )

        group_ids = [
            group["id"]
            for group in groups
        ]

        if not has_status:
            return {
                "kind": "work_type",
                "work_type": work_type,
                "known": False,
                "planned": None,
                "completed": None,
                "remaining": None,
                "complete": None,
                "quantity_type": quantity_type,
                "production_groups": group_ids,
            }

        return {
            "kind": "work_type",
            "work_type": work_type,
            "known": True,
            "planned": total,
            "completed": completed,
            "remaining": missing,
            "complete": missing == 0,
            "quantity_type": quantity_type,
            "production_groups": group_ids,
        }

    @staticmethod
    def _build_main_task(
        *,
        missing_stretches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not missing_stretches:
            return {
                "kind": "task_type",
                "task_type": "hovedledning",
                "known": False,
                "planned": None,
                "completed": None,
                "remaining": None,
                "complete": None,
                "quantity_type": "hovedledning_meter",
            }

        missing_meter = sum(
            float(
                item.get("length_m")
                or 0
            )
            for item in missing_stretches
        )

        return {
            "kind": "task_type",
            "task_type": "hovedledning",
            "known": True,
            "planned": None,
            "completed": None,
            "remaining": missing_meter,
            "complete": False,
            "quantity_type": "hovedledning_meter",
        }

    def _unknown_task(
        self,
        *,
        planned: int | float,
        quantity_type: str,
        task_type: str,
    ) -> dict[str, Any]:
        groups = (
            self.production_group_repository
            .find_groups_for_task_type(
                task_type
            )
        )

        return {
            "kind": "task_type",
            "task_type": task_type,
            "known": False,
            "planned": planned,
            "completed": None,
            "remaining": None,
            "complete": None,
            "quantity_type": quantity_type,
            "production_groups": [
                group["id"]
                for group in groups
            ],
        }