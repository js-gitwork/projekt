from datetime import date

from projektstyring.backend.project_repository import ProjectRepository
from projektstyring.backend.models import (
    Installation,
    Aktivitet,
    Aktivitetstype,
)
from projektstyring.backend.multi_schedule_engine import MultiScheduleEngine
from projektstyring.backend.repositories.team_repository import (
    TeamRepository,
)
from projektstyring.backend.project_rule_resolver import (
    resolve_project_rules,
)


def parse_date(value):
    if not value:
        return None

    if isinstance(value, date):
        return value

    return date.fromisoformat(value)


def find_team_for_installation(
    project: dict,
    task_type: str,
    installation_id: str,
) -> str:
    assignments = project.get("task_assignments", {})
    task_assignments = assignments.get(task_type, [])

    for assignment in task_assignments:
        if installation_id in assignment.get("installations", []):
            return assignment.get("team", "").strip()

    return ""


def build_installations_from_project(project: dict) -> list[Installation]:
    project = resolve_project_rules(project)

    installations = []

    for index, item in enumerate(
        project.get("installations", []),
        start=1,
    ):
        if not item.get("active", True):
            continue

        installation_id = str(item["id"])
        hoveddato = parse_date(item.get("hoveddato"))

        expected_stik = int(item.get("expected_stik") or 0)
        active_stik = int(item.get("active_stik") or 0)
        planned_stik = active_stik or expected_stik
        langhatte = int(item.get("langhatte") or 0)
        korthatte_extra = int(item.get("korthatte_extra") or 0)
        broende = int(item.get("broende") or 0)
        hovedledning_meter = float(
            item.get("hovedledning_meter")
            or item.get("main_length_m")
            or 0
        )

        korthatte_total = langhatte + korthatte_extra

        aktiviteter = []

        hovedledning_hold = find_team_for_installation(
            project,
            "hovedledning",
            installation_id,
        )

        if hoveddato and hovedledning_hold:
            aktiviteter.append(
                Aktivitet(
                    id=f"{installation_id}-hovedledning",
                    installation_id=installation_id,
                    type=Aktivitetstype.HOVEDLEDNING,
                    hold=hovedledning_hold,
                    start_dato=hoveddato,
                )
            )

        if planned_stik > 0:
            stikforberedelse_hold = find_team_for_installation(
                project,
                "stikforberedelse",
                installation_id,
            )

            stik_hold = find_team_for_installation(
                project,
                "stik",
                installation_id,
            )

            kontrol_hold = find_team_for_installation(
                project,
                "kontrol",
                installation_id,
            )

            if stikforberedelse_hold:
                aktiviteter.append(
                    Aktivitet(
                        id=f"{installation_id}-stikforberedelse",
                        installation_id=installation_id,
                        type=Aktivitetstype.STIK_FORBEREDELSE,
                        hold=stikforberedelse_hold,
                        antal_stik=planned_stik,
                    )
                )

            if stik_hold:
                aktiviteter.append(
                    Aktivitet(
                        id=f"{installation_id}-stik",
                        installation_id=installation_id,
                        type=Aktivitetstype.STIK,
                        hold=stik_hold,
                        antal_stik=planned_stik,
                    )
                )

            if kontrol_hold:
                aktiviteter.append(
                    Aktivitet(
                        id=f"{installation_id}-kontrol",
                        installation_id=installation_id,
                        type=Aktivitetstype.KONTROL,
                        hold=kontrol_hold,
                        antal_stik=planned_stik,
                    )
                )

        if korthatte_total > 0:
            korthat_hold = find_team_for_installation(
                project,
                "korthat",
                installation_id,
            )

            if korthat_hold:
                aktiviteter.append(
                    Aktivitet(
                        id=f"{installation_id}-korthat",
                        installation_id=installation_id,
                        type=Aktivitetstype.KORTHAT,
                        hold=korthat_hold,
                        antal_stik=korthatte_total,
                    )
                )

        if broende > 0:
            broend_hold = find_team_for_installation(
                project,
                "broend",
                installation_id,
            )

            if broend_hold:
                aktiviteter.append(
                    Aktivitet(
                        id=f"{installation_id}-broend",
                        installation_id=installation_id,
                        type=Aktivitetstype.BRØND,
                        hold=broend_hold,
                        antal_brønde=broende,
                    )
                )

                    
        dtvk_hold = find_team_for_installation(
            project,
            "dtvk",
            installation_id,
        )

        if dtvk_hold and (hovedledning_meter > 0 or planned_stik > 0):
            aktiviteter.append(
                Aktivitet(
                    id=f"{installation_id}-dtvk",
                    installation_id=installation_id,
                    type=Aktivitetstype.DTVK,
                    hold=dtvk_hold,
                    antal_stik=planned_stik,
                    hovedledning_meter=hovedledning_meter,
                )
            )

        installations.append(
            Installation(
                id=installation_id,
                projekt_id=project["id"],
                rækkefølge=index,
                hovedledning_meter=hovedledning_meter,
                aktiviteter=aktiviteter,
            )
        )

    return installations


def generate_plan_for_project(project: dict):
    teams = TeamRepository().load_team_map()

    engine = MultiScheduleEngine(
        hold_map=teams,
    )

    installations = build_installations_from_project(project)

    return engine.planlæg(installations)


def generate_plan_for_active_projects():
    repo = ProjectRepository()

    active_projects = [
        project
        for project in repo.load_all_projects()
        if project.get("status") == "active"
    ]

    teams = TeamRepository().load_team_map()

    engine = MultiScheduleEngine(
        hold_map=teams,
    )

    installations = []

    for project in active_projects:
        installations.extend(
            build_installations_from_project(project)
        )

    return engine.planlæg(installations)