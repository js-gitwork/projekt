from __future__ import annotations
from datetime import date, datetime
import csv
import io
from decimal import Decimal
from typing import Any

from projektstyring.backend.importers.technical_asset_import import (
    ImportedInstallationAssets,
    ImportedManhole,
    ImportedManholeWork,
    ImportedProjectConstraint,
    ImportedStretch,
    ImportedStretchSurvey,
    TechnicalAssetImport,
)
from projektstyring.backend.importers.deviation_import import (
    DeviationImport,
    ImportedDeviation,
)

PROGRESS_COLUMNS = {
    "opmaaling": "Opmål.%",
    "forarbejde": "Forarb.%",
    "stikopmaaling": "Stikopm.%",
    "hovedledning": "Inst.%",
    "stikaabning": "Stikåbn.",
}


C5_FRACTION_COLUMNS = {
    "korthat": "Korthat",
    "langhat": "Langhat",
    "broendskud": "Brøndskud",
    "raaskud": "Råskud",
    "pkt_rep": "Pkt.rep",
}


def normalize_column_name(value: Any) -> str:
    return (
        str(value or "")
        .replace("\ufeff", "")
        .strip()
    )


def normalize_project_id(value: Any) -> str:
    return str(value or "").strip().upper()

def detect_c5_csv_type(
    csv_text: str,
) -> str:
    """
    Genkender hvilken C5-oversigt CSV-teksten stammer fra.

    project_overview:
        Den almindelige projektoversigt med installationer,
        stræk, survey og produktionsstatus.

    manhole_overview:
        Brøndoversigten med brøndrenovering, udført-data
        og DTVK-oplysninger.
    """
    reader = csv.reader(
        io.StringIO(csv_text),
        delimiter=";",
    )

    try:
        raw_header = next(reader)
    except StopIteration:
        raise ValueError(
            "CSV-dataene er tomme."
        )

    header = {
        normalize_column_name(value)
        for value in raw_header
    }

    manhole_signature = {
        "Brønd 1 renov.",
        "Brønd 1 udført",
        "Brønd 1 init",
        "Brønd 2 udført",
        "Brønd 2 init",
        "DTVK dato",
        "DTVK init",
    }

    deviation_signature = {
        "Afvigenr.",
        "Oprettet",
        "Udført dato",
        "Udført init.",
        "Godkendt",
        "Afvigelse",
        "Type",
    }

    project_signature = {
        "Opmål.%",
        "Forarb.%",
        "Stikopm.%",
        "Inst.%",
        "Stikåbn.",
        "Korthat",
        "Langhat",
        "Brøndskud",
        "Pkt.rep",
    }

    if deviation_signature.issubset(
        header
    ):
        return "deviation_overview"

    if manhole_signature.issubset(
        header
    ):
        return "manhole_overview"

    if project_signature.issubset(
        header
    ):
        return "project_overview"

    raise ValueError(
        "C5 CSV-formatet kunne ikke genkendes. "
        "Filen matcher hverken projektoversigten "
        "eller brøndoversigten."
    )

def parse_c5_date(
    value: Any,
) -> date | None:
    raw = str(value or "").strip()

    if not raw:
        return None

    for fmt in (
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(
                raw,
                fmt,
            ).date()
        except ValueError:
            continue

    return None

def normalize_installation_id(value: Any) -> str:
    value = str(value or "").strip()

    if not value:
        return ""

    value = value.replace(",", ".")

    if value.endswith(".0"):
        value = value[:-2]

    return value


def to_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        value = str(value or "").strip()

        if not value:
            return default

        value = value.replace("%", "")
        value = value.replace(",", ".")

        return int(float(value))

    except (TypeError, ValueError):
        return default


def to_float(
    value: Any,
    default: float | None = 0.0,
) -> float | None:
    try:
        value = str(value or "").strip()

        if not value:
            return default

        value = value.replace("%", "")
        value = value.replace(",", ".")

        return float(value)

    except (TypeError, ValueError):
        return default


def parse_optional_percent(
    value: Any,
) -> float | None:
    """
    Returnerer et procenttal mellem 0 og 100.

    Tomme eller ugyldige felter returneres som None.
    Manglende data må ikke forveksles med 0 procent.
    """
    raw_value = str(value or "").strip()

    if not raw_value:
        return None

    percent = to_float(
        raw_value,
        default=None,
    )

    if percent is None:
        return None

    return max(
        0.0,
        min(100.0, percent),
    )


def clean_c5_fraction(value: Any) -> str:
    """
    Renser C5-værdier som:

        ="3/3"
        "2/0"
        1/1
    """
    value = str(value or "").strip()
    value = value.replace("=", "")
    value = value.replace('"', "")

    return value.strip()


def get_length_m(
    row: dict[str, Any],
) -> float:
    """
    Bruger den nye længde, når den findes.

    Prioritet:
    1. Ny lng.m
    2. Ny længde
    3. Eks.lng
    """
    return (
        to_float(row.get("Ny lng.m"))
        or to_float(row.get("Ny længde"))
        or to_float(row.get("Eks.lng"))
        or 0.0
    )



def to_decimal_or_none(value: Any) -> Decimal | None:
    """Parser en valgfri decimalværdi fra C5."""
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    raw_value = raw_value.replace(",", ".")
    try:
        return Decimal(raw_value)
    except (TypeError, ValueError, ArithmeticError):
        return None


def _find_column_indexes(
    header: list[str],
    column_name: str,
) -> list[int]:
    """
    Finder alle forekomster af et kolonnenavn.

    C5-opmålingsskemaet kan have dublerede kolonnenavne,
    derfor læses surveyfelter positionelt.
    """
    normalized_name = normalize_column_name(
        column_name
    )

    return [
        index
        for index, value in enumerate(header)
        if normalize_column_name(value)
        == normalized_name
    ]


def normalize_c5_manhole_no(
    value: Any,
) -> str:
    """
    Normaliserer et brøndnummer fra C5.

    C5-felter kan i enkelte tilfælde indeholde en kommentar
    efter selve brøndnummeret, fx:

        F57020S (2 stik

    Selve brøndnummeret er da F57020S.

    Andre tegn i brøndnummeret ændres ikke.
    """
    normalized = str(
        value or ""
    ).strip()

    if not normalized:
        return ""

    if " (" in normalized:
        normalized = normalized.split(
            " (",
            1,
        )[0].strip()

    return normalized


def parse_c5_survey_manhole_depth_observations(
    csv_text: str,
    project_id: str,
) -> dict[str, list[Decimal]]:
    """
    Læser alle positive brønddybder fra
    C5-projektoversigten.

    Regler:
    - tomt felt ignoreres
    - 0 eller negativ værdi betyder ingen registreret dybde
    - samme positive værdi flere gange tæller én gang
    - forskellige positive værdier bevares separat,
      så en tastefejl kan rapporteres senere
    """
    reader = csv.reader(
        io.StringIO(csv_text),
        delimiter=";",
    )

    try:
        raw_header = next(reader)
    except StopIteration:
        return {}

    header = [
        normalize_column_name(value)
        for value in raw_header
    ]

    project_indexes = _find_column_indexes(
        header,
        "Projekt",
    )

    manhole_1_indexes = _find_column_indexes(
        header,
        "Brønd 1",
    )

    manhole_2_indexes = _find_column_indexes(
        header,
        "Brønd 2",
    )

    depth_1_indexes = (
        _find_column_indexes(
            header,
            "Brønd 1 dybde",
        )
        + _find_column_indexes(
            header,
            "Dybde brønd 1",
        )
    )

    depth_2_indexes = (
        _find_column_indexes(
            header,
            "Brønd 2 dybde",
        )
        + _find_column_indexes(
            header,
            "Dybde brønd 2",
        )
    )

    if (
        not project_indexes
        or not manhole_1_indexes
        or not manhole_2_indexes
        or not depth_1_indexes
        or not depth_2_indexes
    ):
        return {}

    project_index = project_indexes[0]
    manhole_1_index = manhole_1_indexes[0]
    manhole_2_index = manhole_2_indexes[0]

    normalized_project_id = normalize_project_id(
        project_id
    )

    observations: dict[
        str,
        list[Decimal],
    ] = {}

    def value_at(
        row: list[str],
        index: int,
    ) -> str:
        if index >= len(row):
            return ""

        return str(
            row[index] or ""
        ).strip()

    def add_observations(
        manhole_no: str,
        row: list[str],
        depth_indexes: list[int],
    ) -> None:
        if not manhole_no:
            return

        for depth_index in depth_indexes:
            depth_m = to_decimal_or_none(
                value_at(
                    row,
                    depth_index,
                )
            )

            if (
                depth_m is None
                or depth_m <= 0
            ):
                continue

            values = observations.setdefault(
                manhole_no,
                [],
            )

            if depth_m not in values:
                values.append(
                    depth_m
                )

    for row in reader:
        row_project_id = normalize_project_id(
            value_at(
                row,
                project_index,
            )
        )

        if (
            row_project_id
            != normalized_project_id
        ):
            continue

        manhole_1_no = normalize_c5_manhole_no(
            value_at(
                row,
                manhole_1_index,
            )
        )

        manhole_2_no = normalize_c5_manhole_no(
            value_at(
                row,
                manhole_2_index,
            )
        )

        add_observations(
            manhole_1_no,
            row,
            depth_1_indexes,
        )

        add_observations(
            manhole_2_no,
            row,
            depth_2_indexes,
        )

    return observations


def parse_c5_survey_manhole_depths(
    csv_text: str,
    project_id: str,
) -> dict[str, Decimal]:
    """
    Returnerer kun entydige positive brønddybder.

    Hvis samme brønd har flere forskellige positive
    dybdemål i C5, returneres ingen dybde for brønden.

    Konflikten håndteres senere i importkæden ud fra
    depth_observations_m.
    """
    observations = (
        parse_c5_survey_manhole_depth_observations(
            csv_text=csv_text,
            project_id=project_id,
        )
    )

    return {
        manhole_no: values[0]
        for manhole_no, values
        in observations.items()
        if len(values) == 1
    }
def create_installation_item(
    project_id: str,
    installation_id: str,
    address: str = "",
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "id": installation_id,
        "address": address,
        "stretches": [],
        "_manhole_numbers": set(),
        "expected_stik": 0,
        "main_length_m": 0.0,
        "hovedledning_meter": 0.0,
        "bronde_total": 0,
        "progress": {},
        "c5_values": {
            "korthat": [],
            "langhat": [],
            "broendskud": [],
            "raaskud": [],
            "pkt_rep": [],
        },
        "notes": [],
        "_progress_totals": {
            key: 0.0
            for key in PROGRESS_COLUMNS
        },
        "_progress_weights": {
            key: 0.0
            for key in PROGRESS_COLUMNS
        },
    }


def add_weighted_progress(
    item: dict[str, Any],
    progress_key: str,
    value: Any,
    weight: float,
) -> None:
    percent = parse_optional_percent(value)

    if percent is None:
        return

    effective_weight = (
        weight
        if weight > 0
        else 1.0
    )

    item["_progress_totals"][progress_key] += (
        percent * effective_weight
    )

    item["_progress_weights"][progress_key] += (
        effective_weight
    )


def finalize_progress(
    item: dict[str, Any],
) -> None:
    progress = {}

    for progress_key in PROGRESS_COLUMNS:
        total = item["_progress_totals"][progress_key]
        weight = item["_progress_weights"][progress_key]

        if weight > 0:
            progress[progress_key] = round(
                total / weight
            )
        else:
            progress[progress_key] = None

    item["progress"] = progress


def finalize_bronds_and_lengths(
    item: dict[str, Any],
) -> None:
    bronde = set(
        item.get("_manhole_numbers", set())
    )

    for stretch in item.get("stretches", []):
        from_brond = stretch.get("from_brond")
        to_brond = stretch.get("to_brond")

        if from_brond:
            bronde.add(from_brond)

        if to_brond:
            bronde.add(to_brond)

    item["bronde_total"] = len(bronde)

    item["main_length_m"] = round(
        item["main_length_m"],
        2,
    )

    item["hovedledning_meter"] = round(
        item["hovedledning_meter"],
        2,
    )

def remove_internal_fields(
    item: dict[str, Any],
) -> None:
    item.pop("_progress_totals", None)
    item.pop("_progress_weights", None)
    item.pop("_manhole_numbers", None)

def parse_c5_csv(
    csv_text: str,
) -> list[dict[str, Any]]:
    """
    Parser C5-CSV til preview-data.

    Denne funktion skriver ikke til databasen.
    Den eksisterende UI-preview kan fortsat bruge resultatet.
    """
    reader = csv.DictReader(
        io.StringIO(csv_text),
        delimiter=";",
    )

    if reader.fieldnames:
        reader.fieldnames = [
            normalize_column_name(name)
            for name in reader.fieldnames
        ]

    installations: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for row in reader:
        row = {
            normalize_column_name(key): value
            for key, value in row.items()
        }

        project_id = normalize_project_id(
            row.get("Projekt")
        )

        if not project_id:
            continue

        if project_id.lower().startswith("total"):
            continue

        installation_id = normalize_installation_id(
            row.get("Inst.nr")
        )

        if not installation_id:
            continue

        installation_key = (
            project_id,
            installation_id,
        )

        address = str(
            row.get("Inst.adresse") or ""
        ).strip()

        item = installations.setdefault(
            installation_key,
            create_installation_item(
                project_id=project_id,
                installation_id=installation_id,
                address=address,
            ),
        )

        if not item["address"] and address:
            item["address"] = address

        from_brond = normalize_c5_manhole_no(
            row.get("Brønd 1")
        )

        to_brond = normalize_c5_manhole_no(
            row.get("Brønd 2")
        )

        if from_brond:
            item["_manhole_numbers"].add(from_brond)

        if to_brond:
            item["_manhole_numbers"].add(to_brond)

        expected_stik = to_int(
            row.get("Stik antal")
        )

        length_m = get_length_m(row)

        item["expected_stik"] += expected_stik
        item["main_length_m"] += length_m
        item["hovedledning_meter"] += length_m

        row_c5_values = {
            c5_key: []
            for c5_key in C5_FRACTION_COLUMNS
        }

        for c5_key, column in C5_FRACTION_COLUMNS.items():
            value = clean_c5_fraction(
                row.get(column)
            )

            if value:
                row_c5_values[c5_key].append(
                    value
                )
                item["c5_values"][c5_key].append(
                    value
                )

        if from_brond and to_brond:
            item["stretches"].append(
                {
                    "from_brond": from_brond,
                    "to_brond": to_brond,
                    "length_m": length_m,
                    "dimension": str(
                        row.get("Ny dim.mm")
                        or row.get("Eks.dim")
                        or ""
                    ).strip(),
                    "material": str(
                        row.get("Eks.mat") or ""
                    ).strip(),
                    "stik": expected_stik,
                    "expected_stik": expected_stik,
                    "progress": {
                        progress_key:
                            parse_optional_percent(
                                row.get(column)
                            )
                        for progress_key, column
                        in PROGRESS_COLUMNS.items()
                    },
                    "c5_values": row_c5_values,
                    "notes": str(
                        row.get("Bemærkninger") or ""
                    ).strip(),
                }
            )

        for progress_key, column in PROGRESS_COLUMNS.items():
            add_weighted_progress(
                item=item,
                progress_key=progress_key,
                value=row.get(column),
                weight=length_m,
            )

        note = str(
            row.get("Bemærkninger") or ""
        ).strip()

        if note:
            item["notes"].append(note)

    result = []

    for item in installations.values():
        finalize_progress(item)
        finalize_bronds_and_lengths(item)
        remove_internal_fields(item)
        result.append(item)

    return result

def parse_c5_manhole_work(
    csv_text: str,
    project_id: str,
) -> list[ImportedManholeWork]:
    """
    Læser brøndrenoveringsstatus fra C5-CSV.

    En brønd registreres som planlagt arbejde, når
    renoveringsfeltet er "Ja".

    Hvis der samtidig findes udført-dato og initialer,
    registreres arbejdet som completed.
    """

    normalized_project_id = normalize_project_id(
        project_id
    )

    reader = csv.DictReader(
        io.StringIO(csv_text),
        delimiter=";",
    )

    if reader.fieldnames:
        normalized_fieldnames = [
            normalize_column_name(name)
            for name in reader.fieldnames
        ]

        ds437_index = 0

        for index, name in enumerate(
            normalized_fieldnames
        ):
            if name != "DS437":
                continue

            ds437_index += 1

            if ds437_index == 1:
                normalized_fieldnames[index] = (
                    "Brønd 1 DS437"
                )
            elif ds437_index == 2:
                normalized_fieldnames[index] = (
                    "Brønd 2 DS437"
                )

        reader.fieldnames = normalized_fieldnames

    result: list[ImportedManholeWork] = []
    seen: set[tuple[str, str]] = set()

    for row in reader:
        row = {
            normalize_column_name(key): value
            for key, value in row.items()
        }

        row_project_id = normalize_project_id(
            row.get("Projekt")
        )

        if (
            row_project_id
            != normalized_project_id
        ):
            continue

        for side in (
            "1",
            "2",
        ):
            manhole_no = normalize_c5_manhole_no(
                row.get(
                    f"Brønd {side}"
                )
            )

            if not manhole_no:
                continue

            renovation_value = str(
                row.get(
                    f"Brønd {side} renov."
                )
                or row.get(
                    f"Brønd {side} renov"
                )
                or ""
            ).strip().casefold()

            ds437_value = str(
                row.get(
                    f"Brønd {side} DS437"
                )
                or ""
            ).strip().casefold()

            yes_values = {
                "ja",
                "yes",
                "1",
                "true",
            }

            is_total = (
                renovation_value in yes_values
            )
            is_ds437 = (
                ds437_value in yes_values
            )

            if is_total:
                renovation_type = "total"
            elif is_ds437:
                renovation_type = "ds437"
            else:
                continue

            performed_date = parse_c5_date(
                row.get(
                    f"Brønd {side} udført"
                )
            )

            performed_by = str(
                row.get(
                    f"Brønd {side} init"
                )
                or ""
            ).strip()

            status = (
                "completed"
                if (
                    performed_date is not None
                    and performed_by
                )
                else "planned"
            )

            source_reference = (
                f"{normalized_project_id}:"
                f"{manhole_no}:"
                "broendrenovering"
            )

            key = (
                manhole_no,
                source_reference,
            )

            if key in seen:
                continue

            seen.add(key)

            result.append(
                ImportedManholeWork(
                    manhole_no=manhole_no,
                    work_type="broendrenovering",
                    status=status,
                    quantity=Decimal("1"),
                    unit="stk",
                    performed_date=performed_date,
                    performed_by=(
                        performed_by
                        or None
                    ),
                    source_reference=(
                        source_reference
                    ),
                    metadata={
                        "source": "c5_csv",
                        "renovation_flag": (
                            renovation_value
                        ),
                        "ds437_flag": (
                            ds437_value
                        ),
                        "renovation_type": (
                            renovation_type
                        ),
                        "installation_no": str(
                            row.get("Inst.nr")
                            or ""
                        ).strip(),
                    },
                )
            )

    return result

def parse_c5_availability_permits(
    csv_text: str,
    project_id: str,
) -> list[ImportedProjectConstraint]:
    """
    Samler C5-rådighedstilladelser fra projektoversigten.

    Én tilladelse kan forekomme på mange installationsrækker.
    Tilladelser samles derfor pr. tilladelsesnummer.

    Funktionen ændrer ikke databasen.
    """
    normalized_project_id = normalize_project_id(
        project_id
    )

    reader = csv.DictReader(
        io.StringIO(csv_text),
        delimiter=";",
    )

    if reader.fieldnames:
        reader.fieldnames = [
            normalize_column_name(name)
            for name in reader.fieldnames
        ]

    permits: dict[str, dict[str, Any]] = {}

    for row in reader:
        row = {
            normalize_column_name(key): value
            for key, value in row.items()
        }

        row_project_id = normalize_project_id(
            row.get("Projekt")
        )

        if row_project_id != normalized_project_id:
            continue

        permit_number = str(
            row.get("Tilladnr.") or ""
        ).strip()

        permit_week = str(
            row.get("Tillad-uge") or ""
        ).strip()

        start_date_raw = str(
            row.get("Tillad-start") or ""
        ).strip()

        end_date_raw = str(
            row.get("Tillad-slut") or ""
        ).strip()

        # En helt tom tilladelsesregistrering betyder:
        # ingen ny information fra C5.
        if not any(
            (
                permit_number,
                permit_week,
                start_date_raw,
                end_date_raw,
            )
        ):
            continue

        # Tilladelser uden nummer kan ikke sikkert
        # aggregeres/idempotent identificeres endnu.
        # De gemmes derfor ikke som constraints.
        if not permit_number:
            continue

        installation_no = normalize_installation_id(
            row.get("Inst.nr")
        )

        permit = permits.setdefault(
            permit_number,
            {
                "installation_nos": set(),
                "permit_weeks": set(),
                "start_date_raw_values": set(),
                "end_date_raw_values": set(),
            },
        )

        if installation_no:
            permit["installation_nos"].add(
                installation_no
            )

        if permit_week:
            permit["permit_weeks"].add(
                permit_week
            )

        if start_date_raw:
            permit["start_date_raw_values"].add(
                start_date_raw
            )

        if end_date_raw:
            permit["end_date_raw_values"].add(
                end_date_raw
            )

    result: list[ImportedProjectConstraint] = []

    for permit_number, permit in sorted(
        permits.items()
    ):
        permit_weeks = sorted(
            permit["permit_weeks"]
        )

        start_date_raw_values = sorted(
            permit["start_date_raw_values"]
        )

        end_date_raw_values = sorted(
            permit["end_date_raw_values"]
        )

        start_date_raw = (
            start_date_raw_values[0]
            if len(start_date_raw_values) == 1
            else ""
        )

        end_date_raw = (
            end_date_raw_values[0]
            if len(end_date_raw_values) == 1
            else ""
        )

        start_date = parse_c5_date(
            start_date_raw
        )

        end_date = parse_c5_date(
            end_date_raw
        )

        metadata = {
            "installation_nos": sorted(
                permit["installation_nos"]
            ),
            "permit_week": (
                permit_weeks[0]
                if len(permit_weeks) == 1
                else None
            ),
            "permit_week_values": permit_weeks,
            "start_date_raw": start_date_raw,
            "end_date_raw": end_date_raw,
            "start_date_raw_values": (
                start_date_raw_values
            ),
            "end_date_raw_values": (
                end_date_raw_values
            ),
            "source": "c5_csv",
        }

        # Vi vælger ikke stiltiende mellem modstridende
        # C5-værdier. Importservicen kan bruge disse
        # observationer til en ikke-blokerende advarsel.
        if len(start_date_raw_values) > 1:
            metadata[
                "conflicting_start_dates"
            ] = True

        if len(end_date_raw_values) > 1:
            metadata[
                "conflicting_end_dates"
            ] = True

        if len(permit_weeks) > 1:
            metadata[
                "conflicting_permit_weeks"
            ] = True

        result.append(
            ImportedProjectConstraint(
                constraint_type=(
                    "availability_permit"
                ),
                reference=permit_number,
                start_date=start_date,
                end_date=end_date,
                source="c5",
                source_reference=permit_number,
                metadata=metadata,
            )
        )

    return result

def parse_c5_missing_permit_references(
    csv_text: str,
    project_id: str,
) -> list[dict[str, Any]]:
    """
    Finder C5-rækker med oplysninger om en rådighedstilladelse,
    men uden Tilladnr.

    Rækkerne kan ikke sikkert oprettes som ProjectConstraint,
    fordi de mangler en stabil identitet. De returneres derfor
    som observationer, så importen kan advare uden at gætte.
    """

    normalized_project_id = normalize_project_id(
        project_id
    )

    reader = csv.DictReader(
        io.StringIO(csv_text),
        delimiter=";",
    )

    if reader.fieldnames:
        reader.fieldnames = [
            normalize_column_name(name)
            for name in reader.fieldnames
        ]

    observations: list[dict[str, Any]] = []

    for row in reader:
        row = {
            normalize_column_name(key): value
            for key, value in row.items()
        }

        if normalize_project_id(
            row.get("Projekt")
        ) != normalized_project_id:
            continue

        permit_number = str(
            row.get("Tilladnr.") or ""
        ).strip()

        permit_week = str(
            row.get("Tillad-uge") or ""
        ).strip()

        start_date_raw = str(
            row.get("Tillad-start") or ""
        ).strip()

        end_date_raw = str(
            row.get("Tillad-slut") or ""
        ).strip()

        # Ingen permitoplysninger overhovedet:
        # der er intet at advare om.
        if not any(
            (
                permit_number,
                permit_week,
                start_date_raw,
                end_date_raw,
            )
        ):
            continue

        # Har rækken et nummer, håndteres den af
        # parse_c5_availability_permits().
        if permit_number:
            continue

        installation_no = normalize_installation_id(
            row.get("Inst.nr")
        )

        observations.append(
            {
                "installation_no": installation_no,
                "permit_week": permit_week,
                "start_date_raw": start_date_raw,
                "end_date_raw": end_date_raw,
            }
        )

    return observations

def parse_c5_survey_import(
    csv_text: str,
    project_id: str,
) -> TechnicalAssetImport:
    """
    Parser C5-opmålingsskemaet til TechnicalAssetImport.

    Opmålingsskemaet er autoritativ kilde for:
    - stræk og brøndnumre
    - eksisterende profil, dimension, materiale og længde
    - planlagt dimension og længde
    - målte A/B-dimensioner ved begge ender af strækket
    - profil og materiale ved begge ender
    - trafik, udførende og bemærkning

    Numerisk 0 i A/B-dimensioner bevares. I C5 betyder 0,
    at dimensionen ikke er opmålt.

    En række med kun én brønd opretter ikke et kunstigt stræk.
    """

    normalized_project_id = normalize_project_id(
        project_id
    )

    reader = csv.reader(
        io.StringIO(csv_text),
        delimiter=";",
    )

    rows = list(reader)

    if not rows:
        raise ValueError(
            "Opmålingsskemaet er tomt."
        )

    header = [
        normalize_column_name(value)
        for value in rows[0]
    ]

    def indexes(
        name: str,
    ) -> list[int]:
        return _find_column_indexes(
            header,
            name,
        )

    def required_index(
        name: str,
        occurrence: int = 0,
    ) -> int:
        found = indexes(name)

        if len(found) <= occurrence:
            raise ValueError(
                "Opmålingsskemaet mangler kolonnen "
                f"'{name}'."
            )

        return found[occurrence]

    def optional_index(
        name: str,
        occurrence: int = 0,
    ) -> int | None:
        found = indexes(name)

        if len(found) <= occurrence:
            return None

        return found[occurrence]

    def value_at(
        row: list[str],
        index: int | None,
    ) -> str:
        if index is None:
            return ""

        if index >= len(row):
            return ""

        return str(
            row[index] or ""
        ).strip()

    project_index = required_index(
        "Projekt"
    )
    installation_index = required_index(
        "Inst.nr"
    )
    address_index = optional_index(
        "Inst.adresse"
    )

    first_manhole_index = required_index(
        "Brønd 1"
    )
    second_manhole_index = required_index(
        "Brønd 2"
    )

    first_cannot_open_index = optional_index(
        "Brønd 1 ej åbnes"
    )
    second_cannot_open_index = optional_index(
        "Brønd 2 ej åbnes"
    )

    existing_profile_index = optional_index(
        "Eks. profil"
    )
    existing_dimension_index = optional_index(
        "Eks. dim."
    )
    existing_material_index = optional_index(
        "Eks. mat."
    )
    existing_length_index = optional_index(
        "Eks. længde"
    )

    planned_dimension_index = optional_index(
        "Ny dim."
    )
    planned_length_index = optional_index(
        "Ny længde"
    )
    traffic_index = optional_index(
        "Trafik"
    )

    first_diameter_index = optional_index(
        "Brønd 1 dia."
    )
    second_diameter_index = optional_index(
        "Brønd 2 dia."
    )

    first_depth_indexes = indexes(
        "Brønd 1 dybde"
    )
    second_depth_indexes = indexes(
        "Brønd 2 dybde"
    )

    # Opmålingsskemaet indeholder normalt dybdekolonnen
    # to gange. Den sidste forekomst hører til den målte
    # brøndinformation sammen med diameteren.
    first_depth_index = (
        first_depth_indexes[-1]
        if first_depth_indexes
        else None
    )
    second_depth_index = (
        second_depth_indexes[-1]
        if second_depth_indexes
        else None
    )

    new_profile_indexes = indexes(
        "Ny profil"
    )
    new_dimension_a_indexes = indexes(
        "Ny dim. A"
    )
    new_dimension_b_indexes = indexes(
        "Ny dim. B"
    )
    new_material_indexes = indexes(
        "Ny mat."
    )

    first_profile_index = (
        new_profile_indexes[0]
        if len(new_profile_indexes) >= 1
        else None
    )
    second_profile_index = (
        new_profile_indexes[1]
        if len(new_profile_indexes) >= 2
        else None
    )

    first_dimension_a_index = (
        new_dimension_a_indexes[0]
        if len(new_dimension_a_indexes) >= 1
        else None
    )
    second_dimension_a_index = (
        new_dimension_a_indexes[1]
        if len(new_dimension_a_indexes) >= 2
        else None
    )

    first_dimension_b_index = (
        new_dimension_b_indexes[0]
        if len(new_dimension_b_indexes) >= 1
        else None
    )
    second_dimension_b_index = (
        new_dimension_b_indexes[1]
        if len(new_dimension_b_indexes) >= 2
        else None
    )

    first_material_index = (
        new_material_indexes[0]
        if len(new_material_indexes) >= 1
        else None
    )
    second_material_index = (
        new_material_indexes[1]
        if len(new_material_indexes) >= 2
        else None
    )

    measured_by_index = optional_index(
        "Opmåling udført"
    )
    notes_index = optional_index(
        "Bemærkning"
    )

    installations: dict[
        str,
        ImportedInstallationAssets,
    ] = {}

    manholes: dict[
        str,
        ImportedManhole,
    ] = {}

    sequence_by_installation: dict[
        str,
        int,
    ] = {}

    matched_rows = 0

    def is_true(
        value: str,
    ) -> bool:
        normalized = value.strip().lower()

        return normalized in {
            "1",
            "ja",
            "j",
            "x",
            "true",
        }

    def register_manhole(
        manhole_no: str,
        diameter_value: str,
        depth_value: str,
    ) -> None:
        if not manhole_no:
            return

        diameter = to_decimal_or_none(
            diameter_value
        )
        depth = to_decimal_or_none(
            depth_value
        )

        existing = manholes.get(
            manhole_no
        )

        if existing is None:
            manholes[manhole_no] = ImportedManhole(
                manhole_no=manhole_no,
                diameter_m=diameter,
                depth_m=depth,
                metadata={
                    "source": "c5_csv",
                    "import_type": "survey",
                },
            )
            return

        # En brønd kan forekomme på flere stræk.
        # Vi overskriver derfor ikke en allerede registreret
        # måling her. Konflikter skal senere valideres og
        # rapporteres i stedet for at blive skjult.

        if (
            existing.diameter_m is None
            and diameter is not None
        ):
            existing.diameter_m = diameter

        if (
            existing.depth_m is None
            and depth is not None
        ):
            existing.depth_m = depth

    for row in rows[1:]:
        row_project_id = normalize_project_id(
            value_at(
                row,
                project_index,
            )
        )

        if (
            row_project_id
            != normalized_project_id
        ):
            continue

        installation_no = normalize_installation_id(
            value_at(
                row,
                installation_index,
            )
        )

        if not installation_no:
            continue

        matched_rows += 1

        first_manhole_no = normalize_c5_manhole_no(
            value_at(
                row,
                first_manhole_index,
            )
        )
        second_manhole_no = normalize_c5_manhole_no(
            value_at(
                row,
                second_manhole_index,
            )
        )

        register_manhole(
            first_manhole_no,
            value_at(
                row,
                first_diameter_index,
            ),
            value_at(
                row,
                first_depth_index,
            ),
        )

        register_manhole(
            second_manhole_no,
            value_at(
                row,
                second_diameter_index,
            ),
            value_at(
                row,
                second_depth_index,
            ),
        )

        installation = installations.get(
            installation_no
        )

        if installation is None:
            installation = ImportedInstallationAssets(
                installation_no=installation_no,
                stretches=[],
            )
            installations[
                installation_no
            ] = installation

        # En enkelt brønd er en gyldig installation,
        # men der findes ikke et stræk uden to ender.
        if (
            not first_manhole_no
            or not second_manhole_no
        ):
            continue

        sequence = (
            sequence_by_installation.get(
                installation_no,
                0,
            )
            + 1
        )

        sequence_by_installation[
            installation_no
        ] = sequence

        existing_length = to_decimal_or_none(
            value_at(
                row,
                existing_length_index,
            )
        )

        planned_length = to_decimal_or_none(
            value_at(
                row,
                planned_length_index,
            )
        )

        existing_dimension = value_at(
            row,
            existing_dimension_index,
        )
        planned_dimension = value_at(
            row,
            planned_dimension_index,
        )

        existing_material = value_at(
            row,
            existing_material_index,
        )

        notes = value_at(
            row,
            notes_index,
        )

        survey = ImportedStretchSurvey(
            existing_profile=value_at(
                row,
                existing_profile_index,
            ),
            existing_dimension=(
                existing_dimension
            ),
            existing_material=(
                existing_material
            ),
            existing_length_m=(
                existing_length
            ),
            planned_dimension=(
                planned_dimension
            ),
            planned_length_m=(
                planned_length
            ),
            traffic=value_at(
                row,
                traffic_index,
            ),
            bottom_cannot_open=is_true(
                value_at(
                    row,
                    first_cannot_open_index,
                )
            ),
            bottom_profile=value_at(
                row,
                first_profile_index,
            ),
            bottom_dimension_a_mm=(
                to_decimal_or_none(
                    value_at(
                        row,
                        first_dimension_a_index,
                    )
                )
            ),
            bottom_dimension_b_mm=(
                to_decimal_or_none(
                    value_at(
                        row,
                        first_dimension_b_index,
                    )
                )
            ),
            bottom_material=value_at(
                row,
                first_material_index,
            ),
            top_cannot_open=is_true(
                value_at(
                    row,
                    second_cannot_open_index,
                )
            ),
            top_profile=value_at(
                row,
                second_profile_index,
            ),
            top_dimension_a_mm=(
                to_decimal_or_none(
                    value_at(
                        row,
                        second_dimension_a_index,
                    )
                )
            ),
            top_dimension_b_mm=(
                to_decimal_or_none(
                    value_at(
                        row,
                        second_dimension_b_index,
                    )
                )
            ),
            top_material=value_at(
                row,
                second_material_index,
            ),
            measured_by=value_at(
                row,
                measured_by_index,
            ),
            notes=notes,
            raw_data={
                "address": value_at(
                    row,
                    address_index,
                ),
                "first_manhole_no": (
                    first_manhole_no
                ),
                "second_manhole_no": (
                    second_manhole_no
                ),
            },
        )

        installation.stretches.append(
            ImportedStretch(
                sequence=sequence,
                bottom_manhole_no=(
                    first_manhole_no
                ),
                top_manhole_no=(
                    second_manhole_no
                ),
                length_m=(
                    planned_length
                    if planned_length is not None
                    else existing_length
                    if existing_length is not None
                    else Decimal("0")
                ),
                dimension=(
                    planned_dimension
                    or existing_dimension
                ),
                material=existing_material,
                notes=notes,
                survey=survey,
            )
        )

    if not matched_rows:
        raise ValueError(
            "Opmålingsskemaet indeholder ingen data "
            f"for projekt '{normalized_project_id}'."
        )

    return TechnicalAssetImport(
        project_id=normalized_project_id,
        source="c5_csv",
        import_type="survey",
        installations=list(
            installations.values()
        ),
        manholes=list(
            manholes.values()
        ),
        metadata={
            "source_format": "c5_csv",
            "installation_count": len(
                installations
            ),
            "manhole_count": len(
                manholes
            ),
            "survey_row_count": (
                matched_rows
            ),
        },
    )



def parse_c5_project_overview_import(
    csv_text: str,
    project_id: str,
) -> TechnicalAssetImport:
    """
    Omsætter C5-opmålings-CSV til den nye normaliserede
    TechnicalAssetImport-model.

    Denne adapter kender C5-formatet.
    Resten af importkæden er kildeuafhængig.
    """
    normalized_project_id = normalize_project_id(
        project_id
    )

    parsed_installations = [
        item
        for item in parse_c5_csv(csv_text)
        if normalize_project_id(
            item.get("project_id")
        ) == normalized_project_id
    ]

    if not parsed_installations:
        raise ValueError(
            "CSV-filen indeholder ingen data for projekt "
            f"'{normalized_project_id}'."
        )

    survey_manhole_depths = parse_c5_survey_manhole_depths(
        csv_text=csv_text,
        project_id=normalized_project_id,
    )

    survey_manhole_depth_observations = (
        parse_c5_survey_manhole_depth_observations(
            csv_text=csv_text,
            project_id=normalized_project_id,
        )
    )

    manhole_work = parse_c5_manhole_work(
        csv_text=csv_text,
        project_id=normalized_project_id,
    )

    project_constraints = (
        parse_c5_availability_permits(
            csv_text=csv_text,
            project_id=normalized_project_id,
        )
    )

    missing_permit_references = (
        parse_c5_missing_permit_references(
            csv_text=csv_text,
            project_id=normalized_project_id,
        )
    )

    manhole_numbers: set[str] = set()
    imported_installations = []

    for installation in parsed_installations:
        imported_stretches = []

        for sequence, stretch in enumerate(
            installation.get("stretches", []),
            start=1,
        ):
            bottom_manhole_no = str(
                stretch.get("from_brond") or ""
            ).strip()

            top_manhole_no = str(
                stretch.get("to_brond") or ""
            ).strip()

            if not bottom_manhole_no:
                raise ValueError(
                    "Et stræk mangler bundbrønd på "
                    f"installation '{installation['id']}'."
                )

            if not top_manhole_no:
                raise ValueError(
                    "Et stræk mangler topbrønd på "
                    f"installation '{installation['id']}'."
                )

            manhole_numbers.add(
                bottom_manhole_no
            )
            manhole_numbers.add(
                top_manhole_no
            )

            metadata = {
                "expected_stik": stretch.get(
                    "expected_stik",
                    0,
                ),
                "progress": dict(
                    stretch.get("progress") or {}
                ),
                "c5_values": {
                    str(key): list(value)
                    if isinstance(value, list)
                    else value
                    for key, value in (
                        stretch.get("c5_values")
                        or {}
                    ).items()
                },
            }

            imported_stretches.append(
                ImportedStretch(
                    sequence=sequence,
                    bottom_manhole_no=(
                        bottom_manhole_no
                    ),
                    top_manhole_no=(
                        top_manhole_no
                    ),
                    length_m=Decimal(
                        str(
                            stretch.get(
                                "length_m",
                                0.0,
                            )
                        )
                    ),
                    dimension=str(
                        stretch.get(
                            "dimension",
                            "",
                        )
                    ).strip(),
                    material=str(
                        stretch.get(
                            "material",
                            "",
                        )
                    ).strip(),
                    notes=str(
                        stretch.get(
                            "notes",
                            "",
                        )
                    ).strip(),
                    metadata=metadata,
                )
            )

        imported_installations.append(
            ImportedInstallationAssets(
                installation_no=str(
                    installation["id"]
                ),
                stretches=imported_stretches,
            )
        )

    manholes = [
        ImportedManhole(
            manhole_no=manhole_no,
            depth_m=survey_manhole_depths.get(
                manhole_no
            ),
            metadata={
                "source": "c5_csv",
                "import_type": "project_overview",
                "depth_authoritative": True,
                "depth_observations_m": [
                    str(value)
                    for value in (
                        survey_manhole_depth_observations.get(
                            manhole_no,
                            []
                        )
                    )
                ],
                "depth_source": (
                    "c5_project_overview"
                    if manhole_no
                    in survey_manhole_depths
                    else None
                ),
            },
        )
        for manhole_no in sorted(
            manhole_numbers
        )
    ]

    return TechnicalAssetImport(
        project_id=normalized_project_id,
        source="c5_csv",
        import_type="project_overview",
        installations=imported_installations,
        manholes=manholes,
        manhole_work=manhole_work,
        project_constraints=project_constraints,
        metadata={
            "installation_count": len(
                imported_installations
            ),
            "source_format": "c5_csv",
            "survey_manhole_depth_count": len(
                survey_manhole_depths
            ),
            "missing_permit_references": (
                missing_permit_references
            ),
        },
    )

def parse_c5_manhole_overview_import(
    csv_text: str,
    project_id: str,
) -> TechnicalAssetImport:
    """
    Omsætter C5's brøndoversigt til TechnicalAssetImport.

    Denne importtype opretter eller beriger brønde og
    importerer brøndspecifikt arbejde.

    Den opretter eller ændrer ikke installationer og stræk.
    """
    normalized_project_id = normalize_project_id(
        project_id
    )

    reader = csv.DictReader(
        io.StringIO(csv_text),
        delimiter=";",
    )

    if reader.fieldnames:
        reader.fieldnames = [
            normalize_column_name(name)
            for name in reader.fieldnames
        ]

    manhole_numbers: set[str] = set()

    for row in reader:
        row = {
            normalize_column_name(key): value
            for key, value in row.items()
        }

        if normalize_project_id(
            row.get("Projekt")
        ) != normalized_project_id:
            continue

        for column in (
            "Brønd 1",
            "Brønd 2",
        ):
            manhole_no = normalize_c5_manhole_no(
                row.get(column)
            )

            if manhole_no:
                manhole_numbers.add(
                    manhole_no
                )

    if not manhole_numbers:
        raise ValueError(
            "Brøndoversigten indeholder ingen "
            f"brønde for projekt "
            f"'{normalized_project_id}'."
        )

    survey_manhole_depths = (
        parse_c5_survey_manhole_depths(
            csv_text=csv_text,
            project_id=normalized_project_id,
        )
    )

    survey_manhole_depth_observations = (
        parse_c5_survey_manhole_depth_observations(
            csv_text=csv_text,
            project_id=normalized_project_id,
        )
    )

    manhole_work = parse_c5_manhole_work(
        csv_text=csv_text,
        project_id=normalized_project_id,
    )

    manholes = [
        ImportedManhole(
            manhole_no=manhole_no,
            depth_m=survey_manhole_depths.get(
                manhole_no
            ),
            metadata={
                "source": "c5_csv",
                "import_type": (
                    "manhole_overview"
                ),
                "depth_authoritative": False,
                "depth_observations_m": [
                    str(value)
                    for value in (
                        survey_manhole_depth_observations.get(
                            manhole_no,
                            []
                        )
                    )
                ],
                "depth_source": (
                    "c5_manhole_overview"
                    if manhole_no
                    in survey_manhole_depths
                    else None
                ),
            },
        )
        for manhole_no in sorted(
            manhole_numbers
        )
    ]

    return TechnicalAssetImport(
        project_id=normalized_project_id,
        source="c5_csv",
        import_type="manhole_overview",
        installations=[],
        manholes=manholes,
        manhole_work=manhole_work,
        metadata={
            "source_format": "c5_csv",
            "import_type": (
                "manhole_overview"
            ),
            "manhole_count": len(
                manholes
            ),
            "survey_manhole_depth_count": len(
                survey_manhole_depths
            ),
        },
    )

def parse_c5_deviation_import(
    csv_text: str,
    project_id: str,
) -> DeviationImport:
    """
    Omsætter C5's afvigelsesoversigt til DeviationImport.

    C5-filen indeholder afvigelsens livscyklus:
    oprettet, udført og godkendt.

    Afvigelser er ikke en del af den normale planlægningsmotor.
    """

    normalized_project_id = normalize_project_id(
        project_id
    )

    reader = csv.DictReader(
        io.StringIO(csv_text),
        delimiter=";",
    )

    if reader.fieldnames:
        reader.fieldnames = [
            normalize_column_name(name)
            for name in reader.fieldnames
        ]

    deviations: list[ImportedDeviation] = []

    for row in reader:
        row = {
            normalize_column_name(key): value
            for key, value in row.items()
        }

        row_project_id = normalize_project_id(
            row.get("Projekt")
        )

        if row_project_id != normalized_project_id:
            continue

        deviation_number = str(
            row.get("Afvigenr.") or ""
        ).strip()

        if not deviation_number:
            continue

        installation_no = normalize_installation_id(
            row.get("Inst.nr")
        )

        bottom_manhole_no = normalize_c5_manhole_no(
            row.get("Brønd 1")
        )

        top_manhole_no = normalize_c5_manhole_no(
            row.get("Brønd 2")
        )

        dimension_raw = str(
            row.get("Dim") or ""
        ).strip()

        dimension_mm = None

        if dimension_raw:
            try:
                dimension_mm = int(
                    float(
                        dimension_raw.replace(
                            ",",
                            ".",
                        )
                    )
                )
            except ValueError:
                dimension_mm = None

        deviation_type = str(
            row.get("Type") or ""
        ).strip()

        description = str(
            row.get("Afvigelse") or ""
        ).strip()

        completed_by = str(
            row.get("Udført init.") or ""
        ).strip() or None

        reported_date_raw = str(
            row.get("Oprettet") or ""
        ).strip()

        completed_date_raw = str(
            row.get("Udført dato") or ""
        ).strip()

        approved_date_raw = str(
            row.get("Godkendt") or ""
        ).strip()

        deviations.append(
            ImportedDeviation(
                deviation_number=deviation_number,
                installation_no=(
                    installation_no or None
                ),
                bottom_manhole_no=(
                    bottom_manhole_no or None
                ),
                top_manhole_no=(
                    top_manhole_no or None
                ),
                dimension_mm=dimension_mm,
                deviation_type=deviation_type,
                description=description,
                reported_date=parse_c5_date(
                    reported_date_raw
                ),
                completed_date=parse_c5_date(
                    completed_date_raw
                ),
                completed_by=completed_by,
                approved_date=parse_c5_date(
                    approved_date_raw
                ),
                source_reference=(
                    deviation_number
                ),
                metadata={
                    "source": "c5_csv",
                    "import_type": (
                        "deviation_overview"
                    ),
                    "project_manager": str(
                        row.get("Projektleder")
                        or ""
                    ).strip(),
                    "tender_post_no": str(
                        row.get("Udbud postnr.")
                        or ""
                    ).strip(),
                    "drawing": str(
                        row.get("Udbud tegning")
                        or ""
                    ).strip(),
                    "address": str(
                        row.get("Inst.adresse")
                        or ""
                    ).strip(),
                    "installation_no_raw": str(
                        row.get("Inst.nr")
                        or ""
                    ).strip(),
                    "bottom_manhole_no_raw": str(
                        row.get("Brønd 1")
                        or ""
                    ).strip(),
                    "top_manhole_no_raw": str(
                        row.get("Brønd 2")
                        or ""
                    ).strip(),
                    "reported_date_raw": (
                        reported_date_raw
                    ),
                    "completed_date_raw": (
                        completed_date_raw
                    ),
                    "approved_date_raw": (
                        approved_date_raw
                    ),
                },
            )
        )

    if not deviations:
        raise ValueError(
            "Afvigelsesoversigten indeholder ingen "
            f"afvigelser for projekt "
            f"'{normalized_project_id}'."
        )

    return DeviationImport(
        project_id=normalized_project_id,
        source="c5_csv",
        import_type="deviation_overview",
        deviations=deviations,
        metadata={
            "source_format": "c5_csv",
            "import_type": "deviation_overview",
            "deviation_count": len(
                deviations
            ),
        },
    )

def parse_c5_import(
    csv_text: str,
    project_id: str,
) -> TechnicalAssetImport | DeviationImport:
    """
    Fælles C5-indgang.

    CSV-typen genkendes automatisk ud fra headeren,
    hvorefter den korrekte importmodel oprettes.
    """

    import_type = detect_c5_csv_type(
        csv_text
    )

    if import_type == "project_overview":
        return parse_c5_project_overview_import(
            csv_text=csv_text,
            project_id=project_id,
        )

    if import_type == "manhole_overview":
        return parse_c5_manhole_overview_import(
            csv_text=csv_text,
            project_id=project_id,
        )

    if import_type == "deviation_overview":
        return parse_c5_deviation_import(
            csv_text=csv_text,
            project_id=project_id,
        )

    raise ValueError(
        "Ukendt C5-importtype: "
        f"{import_type}"
    )

def parse_c5_technical_asset_import(
    csv_text: str,
    project_id: str,
) -> TechnicalAssetImport:
    """
    Bagudkompatibel indgang til de tekniske C5-importer.

    Afvigelsesoversigter skal bruge parse_c5_import().
    """

    result = parse_c5_import(
        csv_text=csv_text,
        project_id=project_id,
    )

    if isinstance(
        result,
        DeviationImport,
    ):
        raise ValueError(
            "Afvigelsesoversigten er ikke en "
            "TechnicalAssetImport."
        )

    return result