from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from projektstyring.backend.c5_sync.reader import (
    C5_DATASET,
    connect,
)


MAX_ROWS = 100

# Første godkendte datakilder.
# Udvides efter kontrol af tabelindhold og brugerrettigheder.
ALLOWED_TABLES = {
    "ETPROKONTROL",
    "ETPROKONPOST",
}

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    return value


def clean_text(value: Any) -> str:
    text = str(value or "")

    return "".join(
        char for char in text
        if char.isprintable() or char in "\n\t"
    ).strip()


def get_schema(table: str) -> list[dict]:
    """
    Hent kolonner for en godkendt C5-tabel.
    """
    table = str(table).upper().strip()

    if table not in ALLOWED_TABLES:
        raise ValueError("Tabellen er ikke godkendt til AI-læsning.")

    connection = connect()

    try:
        cursor = connection.cursor(as_dict=True)
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            ("dbo", table),
        )
        return cursor.fetchall()
    finally:
        connection.close()


def find_tables(search: str = "") -> list[dict]:
    """
    Find relevante kolonner i godkendte C5-tabeller.
    """
    needle = str(search).casefold()
    result = []

    for table in sorted(ALLOWED_TABLES):
        for column in get_schema(table):
            if (
                needle in table.casefold()
                or needle in column["COLUMN_NAME"].casefold()
            ):
                result.append({
                    "table": table,
                    "column": column["COLUMN_NAME"],
                    "data_type": column["DATA_TYPE"],
                })

    return result


def read_c5(
    *,
    table: str,
    project_id: str,
    columns: list[str],
    filters: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    Læs projektdata fra en godkendt C5-tabel.

    SQL bygges udelukkende af validerede kolonnenavne.
    Alle filterværdier sendes som SQL-parametre.
    """

    table = str(table).upper().strip()
    project_id = str(project_id).strip()

    if table not in ALLOWED_TABLES:
        raise ValueError("Ikke-godkendt C5-tabel.")

    if not re.fullmatch(r"V[0-9A-Za-z_-]{1,30}", project_id):
        raise ValueError("Ugyldigt projektnummer.")

    if not isinstance(columns, list) or not columns:
        raise ValueError("Mindst én kolonne skal angives.")

    if not isinstance(limit, int) or not 1 <= limit <= MAX_ROWS:
        raise ValueError("Ugyldig resultatgrænse.")

    if type(offset) is not int or offset < 0 or offset > 100000:
        raise ValueError("Ugyldigt offset.")

    schema = get_schema(table)

    available = {
        item["COLUMN_NAME"].upper(): item["COLUMN_NAME"]
        for item in schema
    }

    requested = []

    for column in columns:
        key = str(column).upper().strip()

        if key not in available:
            raise ValueError(f"Ukendt kolonne: {column}")

        if not IDENTIFIER.fullmatch(available[key]):
            raise ValueError("Ugyldigt kolonnenavn.")

        if key not in requested:
            requested.append(key)

    filters = filters or {}

    if not isinstance(filters, dict):
        raise ValueError("Filtre skal være et objekt.")

    conditions = [
        "[DATASET] = %s",
        "LTRIM(RTRIM([PROJNUMBER])) = %s",
    ]

    parameters = [C5_DATASET, project_id]

    for column, value in filters.items():
        key = str(column).upper().strip()

        if key not in available:
            raise ValueError(f"Ukendt filterkolonne: {column}")

        if key in {"DATASET", "PROJNUMBER"}:
            raise ValueError("Projektfilter kan ikke overskrives.")

        name = available[key]

        if not IDENTIFIER.fullmatch(name):
            raise ValueError("Ugyldigt filterkolonnenavn.")

        if value is None:
            conditions.append(f"[{name}] IS NULL")
        elif isinstance(value, (str, int, float, bool, Decimal)):
            conditions.append(f"[{name}] = %s")
            parameters.append(value)
        else:
            raise ValueError("Ikke-understøttet filterværdi.")

    select_columns = ", ".join(
        f"[{available[key]}]"
        for key in requested
    )

    where_clause = " AND ".join(conditions)

    sql = (
        f"SELECT {select_columns} "
        f"FROM [dbo].[{table}] "
        f"WHERE {where_clause} "
        f"ORDER BY [ROWNUMBER] "
        f"OFFSET %s ROWS FETCH NEXT %s ROWS ONLY"
    )

    count_sql = (
        f"SELECT COUNT(*) AS total "
        f"FROM [dbo].[{table}] "
        f"WHERE {where_clause}"
    )

    connection = connect()

    try:
        cursor = connection.cursor(as_dict=True)
        cursor.execute(count_sql, tuple(parameters))
        total = cursor.fetchone()["total"]

        cursor.execute(sql, tuple(parameters + [offset, limit]))

        rows = [
            {
                key: (
                    clean_text(value)
                    if isinstance(value, str)
                    else normalize_value(value)
                )
                for key, value in row.items()
            }
            for row in cursor.fetchall()
        ]

        return {
            "source": "c5",
            "table": table,
            "project_id": project_id,
            "rows": rows,
            "returned_rows": len(rows),
            "limit": limit,
            "offset": offset,
            "total_rows": total,
            "has_more": offset + len(rows) < total,
            "may_be_truncated": offset + len(rows) < total,
        }

    finally:
        connection.close()
