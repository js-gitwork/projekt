import csv
import io


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


def normalize_column_name(value):
    return (
        str(value or "")
        .replace("\ufeff", "")
        .strip()
    )


def normalize_project_id(value):
    return str(value or "").strip().upper()


def normalize_installation_id(value):
    value = str(value or "").strip()

    if not value:
        return ""

    value = value.replace(",", ".")

    if value.endswith(".0"):
        value = value[:-2]

    return value


def to_int(value, default=0):
    try:
        value = str(value or "").strip()

        if not value:
            return default

        value = value.replace("%", "")
        value = value.replace(",", ".")

        return int(float(value))

    except (TypeError, ValueError):
        return default


def to_float(value, default=0.0):
    try:
        value = str(value or "").strip()

        if not value:
            return default

        value = value.replace("%", "")
        value = value.replace(",", ".")

        return float(value)

    except (TypeError, ValueError):
        return default


def parse_optional_percent(value):
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


def clean_c5_fraction(value):
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


def get_length_m(row):
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


def create_installation_item(
    project_id,
    installation_id,
    address="",
):
    return {
        "project_id": project_id,
        "id": installation_id,
        "address": address,
        "stretches": [],
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
    item,
    progress_key,
    value,
    weight,
):
    """
    Aggregerer procentfelter på tværs af en installations strækninger.

    Stræklængden bruges som vægt, når den findes.
    Hvis længden mangler, vægtes rækken som 1.
    """

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


def finalize_progress(item):
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


def finalize_bronds_and_lengths(item):
    bronde = set()

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


def remove_internal_fields(item):
    item.pop("_progress_totals", None)
    item.pop("_progress_weights", None)


def parse_c5_csv(csv_text):
    reader = csv.DictReader(
        io.StringIO(csv_text),
        delimiter=";",
    )

    if reader.fieldnames:
        reader.fieldnames = [
            normalize_column_name(name)
            for name in reader.fieldnames
        ]

    installations = {}

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

        from_brond = str(
            row.get("Brønd 1") or ""
        ).strip()

        to_brond = str(
            row.get("Brønd 2") or ""
        ).strip()

        expected_stik = to_int(
            row.get("Stik antal")
        )

        length_m = get_length_m(row)

        item["expected_stik"] += expected_stik
        item["main_length_m"] += length_m
        item["hovedledning_meter"] += length_m

        if from_brond or to_brond or length_m:
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
                        progress_key: parse_optional_percent(
                            row.get(column)
                        )
                        for progress_key, column
                        in PROGRESS_COLUMNS.items()
                    },
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

        for c5_key, column in C5_FRACTION_COLUMNS.items():
            value = clean_c5_fraction(
                row.get(column)
            )

            if value:
                item["c5_values"][c5_key].append(
                    value
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


def create_project_installation(installation_id):
    return {
        "id": installation_id,
        "active": True,
        "hoveddato": None,
        "expected_stik": 0,

        # Disse værdier kommer ikke fra C5-feltet Stikåbn.
        # De må derfor ikke udledes eller overskrives af denne import.
        "active_stik": None,
        "opened_stik": None,

        "langhatte": 0,
        "korthatte_extra": 0,
        "broende": 0,
        "main_length_m": 0.0,
        "hovedledning_meter": 0.0,
        "bronde_total": 0,
        "stretches": [],
        "progress": {},
        "c5_values": {},
        "notes": "",
    }


def build_installation_notes(update):
    notes = []

    if update.get("address"):
        notes.append(
            update["address"]
        )

    stretch_texts = []

    for stretch in update.get("stretches", []):
        from_brond = stretch.get(
            "from_brond",
            "",
        )

        to_brond = stretch.get(
            "to_brond",
            "",
        )

        length_m = stretch.get(
            "length_m",
            0,
        )

        if from_brond or to_brond:
            stretch_texts.append(
                f"{from_brond}-{to_brond} ({length_m} m)"
            )

    if stretch_texts:
        notes.append(
            "Strækninger: "
            + ", ".join(stretch_texts)
        )

    if update.get("notes"):
        notes.append(
            "Bemærkninger: "
            + " | ".join(update["notes"])
        )

    return " | ".join(notes)


def apply_c5_updates_to_project(project, updates):
    project_id = normalize_project_id(
        project.get("id")
    )

    existing = {
        normalize_installation_id(
            item.get("id")
        ): item
        for item in project.get(
            "installations",
            [],
        )
    }

    for update in updates:
        update_project_id = normalize_project_id(
            update.get("project_id")
        )

        # Data fra andre projekter må aldrig overføres.
        if (
            project_id
            and update_project_id
            and project_id != update_project_id
        ):
            continue

        installation_id = normalize_installation_id(
            update.get("id")
        )

        if not installation_id:
            continue

        installation = existing.get(
            installation_id
        )

        if not installation:
            installation = create_project_installation(
                installation_id
            )

            project.setdefault(
                "installations",
                [],
            ).append(installation)

            existing[installation_id] = installation

        installation["expected_stik"] = update.get(
            "expected_stik",
            0,
        )

        # active_stik og opened_stik overskrives ikke.
        # C5-kolonnen Stikåbn. er en procentværdi og indeholder
        # ikke de to underliggende stikantal.

        installation["main_length_m"] = update.get(
            "main_length_m",
            0.0,
        )

        installation["hovedledning_meter"] = update.get(
            "hovedledning_meter",
            0.0,
        )

        installation["bronde_total"] = update.get(
            "bronde_total",
            0,
        )

        installation["stretches"] = update.get(
            "stretches",
            [],
        )

        installation["progress"] = update.get(
            "progress",
            {},
        )

        installation["c5_values"] = update.get(
            "c5_values",
            {},
        )

        installation["notes"] = build_installation_notes(
            update
        )

    return project