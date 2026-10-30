
from __future__ import annotations

import getpass
import os
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

import pymssql


C5_HOST = "192.168.0.36"
C5_PORT = 49854
C5_DATABASE = "c5sql"
C5_DATASET = "VPO"

MAINLINE_TYPES = (0, 6, 7)


def clean(value: object) -> str:
    return str(value or "").strip()


def valid_date(value: object) -> bool:
    if value is None:
        return False

    if isinstance(value, datetime):
        return value.year > 1900

    return False


def connect():
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(
        Path(__file__).resolve().parents[3] / ".env"
    )

    username = os.environ["C5_USERNAME"]
    password = os.environ["C5_PASSWORD"]

    return pymssql.connect(
        server=os.environ["C5_HOST"],
        port=int(os.environ["C5_PORT"]),
        user=username,
        password=password,
        database=os.environ["C5_DATABASE"],
        charset="UTF-8",
        login_timeout=10,
        timeout=30,
        as_dict=True,
    )


def read_project(connection, project_id: str) -> dict | None:
    """
    Henter projektets stamoplysninger fra C5.

    PROJTABLE.NAME er kundenavnet.
    Selve projektnavnet afklares under projektoprettelsen.
    """
    sql = """
        SELECT
            NUMBER_,
            NAME,
            ORDERPHASE,
            ETPROSTATUS
        FROM dbo.PROJTABLE
        WHERE DATASET = %s
          AND LTRIM(RTRIM(NUMBER_)) = %s
    """

    cursor = connection.cursor()

    try:
        cursor.execute(sql, (C5_DATASET, project_id))
        rows = cursor.fetchall()
    finally:
        cursor.close()

    if not rows:
        return None

    if len(rows) != 1:
        raise ValueError(
            f"Flere C5-projekter matcher {project_id}."
        )

    row = rows[0]

    return {
        "project_id": clean(row["NUMBER_"]),
        "customer": clean(row["NAME"]),
        "c5_order_phase": row["ORDERPHASE"],
        "c5_production_status": row["ETPROSTATUS"],
    }


def read_stretches(connection, project_id: str) -> list[dict]:
    """
    Læser brøndstræk og brøndrenoveringsregistreringer
    fra C5 for ét projekt.

    Læser kun. Ændrer aldrig C5.
    """
    sql = """
        SELECT
            ROWNUMBER,
            LINENUMBER,
            POSITIONTXT,
            INSTEJER,
            BRXND1,
            BRXND2,
            NYLEDDIM,
            NYLEDTVLXNGDE,
            TVKONTROLGODKENDT,
            INSTALLATIONDATO,

            BRXND1RENOV,
            BRXND1RENOVDATO,
            BRXND1RENOVINIT,
            BR1DS437,

            BRXND2RENOV,
            BRXND2RENOVDATO,
            BRXND2RENOVINIT,
            BR2DS437,

            DS437
        FROM dbo.ETPROKONTROL
        WHERE DATASET = %s
          AND LTRIM(RTRIM(PROJNUMBER)) = %s
        ORDER BY LINENUMBER, ROWNUMBER
    """

    cursor = connection.cursor()

    try:
        cursor.execute(sql, ("VPO", project_id))
        return list(cursor.fetchall())
    finally:
        cursor.close()

def read_service_work(connection, project_id: str) -> list[dict]:
    sql = """
        SELECT
            ROWNUMBER,
            REFID,
            STIKNUMMER,
            STIKLH,
            RENOVLNG,
            STIKKH,
            STIKBRXND,
            FXRDIGDATO
        FROM dbo.ETPROKONPOST
        WHERE DATASET = %s
          AND LTRIM(RTRIM(PROJNUMBER)) = %s
        ORDER BY ROWNUMBER
    """

    cursor = connection.cursor()
    try:
        cursor.execute(sql, (C5_DATASET, project_id))
        return list(cursor.fetchall())
    finally:
        cursor.close()


def report(
    project_id: str,
    stretches: list[dict],
    service_work: list[dict],
) -> None:
    groups = defaultdict(list)
    c5_ids = set()

    for stretch in stretches:
        row_id = stretch["ROWNUMBER"]

        if row_id in c5_ids:
            raise ValueError(
                f"Dubleret C5 ROWNUMBER: {row_id}"
            )

        c5_ids.add(row_id)

        if stretch["INSTEJER"] not in MAINLINE_TYPES:
            continue

        installation_no = clean(stretch["POSITIONTXT"])

        if not installation_no:
            raise ValueError(
                f"Manglende POSITIONTXT på C5-række {row_id}"
            )

        groups[installation_no].append(stretch)

    print(f"\n=== {project_id} ===")
    print(f"C5-brøndstræk i alt: {len(stretches)}")
    print(f"Hovedledningsinstallationer: {len(groups)}")

    for installation_no, rows in sorted(groups.items()):
        ready = sum(
            bool(clean(row["TVKONTROLGODKENDT"]))
            for row in rows
        )

        installed = sum(
            valid_date(row["INSTALLATIONDATO"])
            for row in rows
        )

        print(
            f"  Installation {installation_no}: "
            f"{len(rows)} stræk, "
            f"forarbejde {ready}/{len(rows)}, "
            f"installationsdato {installed}/{len(rows)}"
        )

    print("\nStikarbejder:")

    for field, label in (
        ("STIKLH", "Langhatte"),
        ("STIKKH", "Korthatte"),
        ("STIKBRXND", "Brøndskud"),
    ):
        planned = [
            row
            for row in service_work
            if row[field] is not None
            and Decimal(str(row[field])) > 0
        ]

        completed = sum(
            valid_date(row["FXRDIGDATO"])
            for row in planned
        )

        print(f"  {label}: {completed}/{len(planned)}")


def main() -> None:
    project_ids = ("V165460", "V166960")

    connection = connect()

    try:
        for project_id in project_ids:
            stretches = read_stretches(
                connection,
                project_id,
            )
            service_work = read_service_work(
                connection,
                project_id,
            )

            report(
                project_id,
                stretches,
                service_work,
            )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
