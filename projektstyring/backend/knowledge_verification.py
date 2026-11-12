
"""
Deterministisk verificering af databasens relationer.

Formål
------
Undersøger om en foreslået sammenkobling mellem to
datasæt faktisk fungerer på de hentede rækker.

AI vælger relationen og undersøgelsens omfang.
Python beregner resultatet uden AI-fortolkning.

Dette modul:
- læser ikke selv databaser
- udfører ikke SQL
- ændrer ikke projektdata
- ændrer ikke verificeringsstatus
- gemmer ikke selv evidens

Den kaldende service skal sikre, at data stammer
fra en autoriseret kilde, og at hele det relevante
datasæt er indlæst.

Et vellykket match er ikke i sig selv dokumentation
for en deklareret foreign key eller feltets
forretningsmæssige betydning.
"""

from __future__ import annotations

from typing import Any


def verify_join(
    *,
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    left_key: str,
    right_key: str,
) -> dict[str, Any]:
    """
    Undersøg relationen left_key = right_key.

    left_rows betragtes som de rækker, der skal
    kunne finde en tilsvarende række i right_rows.

    Resultatet er kun en teknisk matchanalyse.
    Det siger intet om relationens forretningsbetydning.
    """

    if not isinstance(left_rows, list):
        raise ValueError("left_rows skal være en liste.")

    if not isinstance(right_rows, list):
        raise ValueError("right_rows skal være en liste.")

    if not left_key or not right_key:
        raise ValueError("Begge relationsnøgler kræves.")

    for row in left_rows:
        if not isinstance(row, dict) or left_key not in row:
            raise ValueError(
                f"Venstre datasæt mangler feltet {left_key}."
            )

    for row in right_rows:
        if not isinstance(row, dict) or right_key not in row:
            raise ValueError(
                f"Højre datasæt mangler feltet {right_key}."
            )

    # SQL-lignende sammenligning: NULL matcher ikke NULL.
    # Strenge konverteres ikke til tal eller omvendt.
    def normalize(value: Any) -> tuple[str, Any] | None:
        if value is None:
            return None

        if isinstance(value, bool):
            raise ValueError(
                "Boolean kan ikke bruges som relationsnøgle."
            )

        if isinstance(value, (str, int, float)):
            return (type(value).__name__, value)

        raise ValueError(
            "Relationsnøglen har en ikke-understøttet datatype."
        )

    right_counts: dict[tuple[str, Any], int] = {}

    right_nulls = 0

    for row in right_rows:
        key = normalize(row[right_key])

        if key is None:
            right_nulls += 1
            continue

        right_counts[key] = right_counts.get(key, 0) + 1

    matched_rows = 0
    unmatched_rows = 0
    left_nulls = 0
    duplicate_matches = 0

    for row in left_rows:
        key = normalize(row[left_key])

        if key is None:
            left_nulls += 1
            continue

        count = right_counts.get(key, 0)

        if count == 0:
            unmatched_rows += 1
        else:
            matched_rows += 1

            if count > 1:
                duplicate_matches += 1

    duplicate_right_keys = sum(
        1 for count in right_counts.values()
        if count > 1
    )

    non_null_left = len(left_rows) - left_nulls

    return {
        "left_key": left_key,
        "right_key": right_key,
        "left_rows": len(left_rows),
        "right_rows": len(right_rows),
        "left_null_keys": left_nulls,
        "right_null_keys": right_nulls,
        "checked_count": non_null_left,
        "matched_count": matched_rows,
        "unmatched_count": unmatched_rows,
        "duplicate_right_keys": duplicate_right_keys,
        "rows_with_multiple_matches": duplicate_matches,
        "match_rate": (
            matched_rows / non_null_left
            if non_null_left
            else None
        ),
        "outcome": (
            "inconclusive"
            if non_null_left == 0
            else "passed"
            if unmatched_rows == 0
            and duplicate_matches == 0
            else "failed"
        ),
    }
