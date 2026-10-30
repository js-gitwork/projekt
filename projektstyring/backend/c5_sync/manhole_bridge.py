
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models import (
    Installation,
    Manhole,
    ManholeWork,
    Project,
)
from projektstyring.backend.db_models.vpmanhole import (
    VPManholeDelivery,
)
from projektstyring.backend.c5_sync.reader import connect, read_stretches


def flag(value: object) -> bool:
    return str(value or "").strip().casefold() in {
        "1", "true", "yes", "ja"
    }


def installation_key(value: object) -> str:
    raw = str(value or "").strip().replace(",", ".")
    if not raw:
        return ""
    try:
        number = Decimal(raw)
        if not number.is_finite():
            return ""
        return format(number.normalize(), "f")
    except InvalidOperation:
        return raw.casefold()


def completed_in_c5(payload: dict, side: int) -> bool:
    raw_date = str(
        payload.get(f"BRXND{side}RENOVDATO") or ""
    ).strip()
    initials = str(
        payload.get(f"BRXND{side}RENOVINIT") or ""
    ).strip()

    try:
        performed = date.fromisoformat(raw_date[:10])
    except ValueError:
        return False

    return performed.year > 1900 and bool(initials)


def collect_requirements(rows):
    """
    Saml C5-markeringer pr. fysisk brønd.
    Begge markeringer giver én fotoopgave.
    """
    result = {}

    for project_id, payload in rows:
        if not isinstance(payload, dict):
            continue

        for side in (1, 2):
            total = flag(payload.get(f"BRXND{side}RENOV"))
            ds437 = flag(payload.get(f"BR{side}DS437"))

            if not (total or ds437):
                continue

            manhole_no = str(
                payload.get(f"BRXND{side}") or ""
            ).strip()

            if not manhole_no:
                continue

            key = (project_id, manhole_no)
            item = result.setdefault(
                key,
                {
                    "project_id": project_id,
                    "manhole_no": manhole_no,
                    "total": False,
                    "ds437": False,
                    "positions": set(),
                    "needs_photos": False,
                    "has_c5_completion": False,
                },
            )

            item["total"] |= total
            item["ds437"] |= ds437

            position = installation_key(
                payload.get("POSITIONTXT")
            )

            if position:
                item["positions"].add(position)

            if completed_in_c5(payload, side):
                item["has_c5_completion"] = True

    for item in result.values():
        item["needs_photos"] = not item["has_c5_completion"]

    return result


def run(*, apply: bool, project_ids: list[str]) -> int:
    counts = defaultdict(int)
    problems = []
    actions = []

    with SessionLocal() as session:
        with session.begin():
            project_query = select(Project).where(
                Project.is_closed.is_(False)
            )

            if project_ids:
                project_query = project_query.where(
                    Project.id.in_(project_ids)
                )

            projects = {
                project.id: project
                for project in session.scalars(
                    project_query
                ).all()
            }

            if not projects:
                print("Ingen åbne projekter fundet.")
                return 0

            # C5 er autoritativ. Ingen lokal C5-kopi.
            rows = []
            c5_connection = connect()

            try:
                for project_id in sorted(projects):
                    for record in read_stretches(
                        c5_connection,
                        project_id,
                    ):
                        rows.append(
                            (project_id, dict(record))
                        )
            finally:
                c5_connection.close()

            requirements = collect_requirements(rows)

            installation_rows = session.scalars(
                select(Installation).where(
                    Installation.project_id.in_(
                        list(projects)
                    )
                )
            ).all()

            installations = defaultdict(dict)

            for installation in installation_rows:
                key = installation_key(
                    installation.installation_no
                )
                if key:
                    installations[
                        installation.project_id
                    ][key] = installation

            manholes = {
                (m.project_id, m.manhole_no): m
                for m in session.scalars(
                    select(Manhole).where(
                        Manhole.project_id.in_(
                            list(projects)
                        )
                    )
                ).all()
            }

            existing_ids = [m.id for m in manholes.values()]

            latest_works = {}
            deliveries = {}

            if existing_ids:
                for work in session.scalars(
                    select(ManholeWork)
                    .where(
                        ManholeWork.manhole_id.in_(
                            existing_ids
                        ),
                        ManholeWork.work_type
                        == "broendrenovering",
                    )
                    .order_by(ManholeWork.id.desc())
                ):
                    latest_works.setdefault(
                        work.manhole_id, work
                    )

                deliveries = {
                    delivery.manhole_id: delivery
                    for delivery in session.scalars(
                        select(VPManholeDelivery).where(
                            VPManholeDelivery.manhole_id.in_(
                                existing_ids
                            )
                        )
                    ).all()
                }

            for key, item in sorted(requirements.items()):
                project_id, manhole_no = key
                manhole = manholes.get(key)

                delivery = (
                    deliveries.get(manhole.id)
                    if manhole is not None
                    else None
                )

                # Afleverede fotoopgaver genåbnes aldrig.
                if delivery is not None and (
                    delivery.is_completed
                    or delivery.completed_at is not None
                    or delivery.photos_purged_at is not None
                ):
                    counts["already_delivered"] += 1
                    continue

                previous = (
                    latest_works.get(manhole.id)
                    if manhole is not None
                    else None
                )

                # Historisk afsluttet C5-arbejde uden en
                # eksisterende fotoopgave importeres ikke.
                if item["has_c5_completion"]:
                    counts["historically_completed"] += 1
                    continue

                available = installations.get(
                    project_id, {}
                )
                matches = sorted(
                    item["positions"] & set(available)
                )

                previous_metadata = (
                    previous.metadata_data or {}
                    if previous is not None
                    else {}
                )
                previous_position = installation_key(
                    previous_metadata.get("installation_no")
                )

                # Bevar den hidtidige installationskobling,
                # hvis den stadig findes i C5.
                if previous_position in matches:
                    chosen = previous_position
                elif len(matches) == 1:
                    chosen = matches[0]
                elif len(matches) > 1:
                    problems.append(
                        f"{project_id} / {manhole_no}: "
                        f"flere installationer {matches}"
                    )
                    continue
                else:
                    problems.append(
                        f"{project_id} / {manhole_no}: "
                        "ingen matchende installation "
                        f"for {sorted(item['positions'])}"
                    )
                    continue

                installation_no = (
                    available[chosen].installation_no
                )

                # VPManholes eksisterende service forventer
                # total eller ds437 som renovation_type.
                # Begge oprindelige flag bevares separat.
                renovation_type = (
                    "ds437"
                    if item["ds437"]
                    else "total"
                )

                new_metadata = {
                    "source": "c5_sql",
                    "installation_no": installation_no,
                    "renovation_type": renovation_type,
                    "ds437_flag": item["ds437"],
                    "renovation_flag": item["total"],
                }

                if previous is not None:
                    same_type = (
                        previous_metadata.get(
                            "renovation_type"
                        ) == renovation_type
                    )
                    same_installation = (
                        previous_position == chosen
                    )
                    same_status = previous.status in {
                        "planned", "completed"
                    }

                    # Den gamle CSV-import kan allerede
                    # have oprettet denne registrering.
                    old_flags = (
                        previous_metadata.get(
                            "ds437_flag"
                        ),
                        previous_metadata.get(
                            "renovation_flag"
                        ),
                    )

                    if all(
                        isinstance(value, bool)
                        for value in old_flags
                    ):
                        same_flags = old_flags == (
                            item["ds437"], item["total"]
                        )
                    else:
                        same_flags = not (
                            item["ds437"] and item["total"]
                        )

                    if (
                        same_type
                        and same_installation
                        and same_status
                        and same_flags
                    ):
                        counts["unchanged"] += 1
                        continue

                action = (
                    "OPRET BRØND"
                    if manhole is None
                    else "OPDATER ARBEJDE"
                )

                actions.append(
                    f"{action}: {project_id} / "
                    f"{manhole_no} / "
                    f"installation {installation_no} / "
                    f"DS437={item['ds437']} "
                    f"Total={item['total']}"
                )

                if not apply:
                    counts["planned_changes"] += 1
                    continue

                if manhole is None:
                    manhole = Manhole(
                        project_id=project_id,
                        manhole_no=manhole_no,
                        active=True,
                        metadata_data={
                            "source": "c5_sql"
                        },
                    )
                    session.add(manhole)
                    session.flush()
                    manholes[key] = manhole
                    counts["new_manholes"] += 1

                new_work = ManholeWork(
                    manhole_id=manhole.id,
                    supersedes_work_id=(
                        previous.id
                        if previous is not None
                        else None
                    ),
                    work_type="broendrenovering",
                    status="planned",
                    quantity=Decimal("1"),
                    unit="stk",
                    source="c5_sql",
                    source_reference=(
                        f"{project_id}:"
                        f"{manhole_no}:broendrenovering"
                    ),
                    metadata_data=new_metadata,
                )

                session.add(new_work)
                counts["new_work_entries"] += 1

            for action in actions:
                print(action)

            for problem in problems:
                print("MANGLER MAPPING:", problem)

            if problems and apply:
                raise RuntimeError(
                    "Import afbrudt. Ingen ændringer "
                    "er gemt, fordi nogle brønde "
                    "mangler entydig installationskobling."
                )

    print("\nResultat:")
    for name, count in sorted(counts.items()):
        print(f"  {name}: {count}")

    print(f"  mapping_problems: {len(problems)}")
    print(
        "\nTilstand:",
        "GEMT" if apply else "FORHÅNDSVISNING",
    )

    return 0 if not problems else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true"
    )
    parser.add_argument(
        "--project", action="append", default=[]
    )
    args = parser.parse_args()

    raise SystemExit(
        run(
            apply=args.apply,
            project_ids=args.project,
        )
    )


if __name__ == "__main__":
    main()
