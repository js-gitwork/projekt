import csv
import io


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
        value = value.replace(",", ".")
        return int(float(value))
    except ValueError:
        return default


def to_float(value, default=0.0):
    try:
        value = str(value or "").strip()
        if not value:
            return default
        value = value.replace(",", ".")
        return float(value)
    except ValueError:
        return default


def parse_percent(value):
    return to_int(value, 0)


def clean_c5_fraction(value):
    value = str(value or "").strip()
    value = value.replace("=", "")
    value = value.replace('"', "")
    return value


def get_length_m(row):
    """
    Projektoversigten har typisk både Eks.lng og Ny lng.m.
    Vi bruger Ny lng.m først, fordi den er mest relevant for arbejdet.
    Hvis den mangler, falder vi tilbage til Eks.lng.
    """
    return (
        to_float(row.get("Ny lng.m"))
        or to_float(row.get("Ny længde"))
        or to_float(row.get("Eks.lng"))
        or 0.0
    )


def parse_c5_csv(csv_text):
    reader = csv.DictReader(
        io.StringIO(csv_text),
        delimiter=";",
    )

    installations = {}

    for row in reader:
        project_id = str(row.get("Projekt", "")).strip()

        if not project_id:
            continue

        if project_id.lower().startswith("total"):
            continue

        installation_id = normalize_installation_id(
            row.get("Inst.nr")
        )

        if not installation_id:
            continue

        item = installations.setdefault(
            installation_id,
            {
                "id": installation_id,
                "address": row.get("Inst.adresse", "").strip(),
                "stretches": [],
                "expected_stik": 0,
                "active_stik": 0,
                "main_length_m": 0.0,
                "hovedledning_meter": 0.0,
                "bronde_total": 0,
                "progress": {
                    "opmaaling": 100,
                    "forarbejde": 100,
                    "stikopmaaling": 100,
                    "hovedledning": 100,
                    "stikaabning": 100,
                },
                "c5_values": {
                    "korthat": [],
                    "langhat": [],
                    "broendskud": [],
                    "raaskud": [],
                    "pkt_rep": [],
                },
                "notes": [],
            },
        )

        from_brond = str(row.get("Brønd 1", "")).strip()
        to_brond = str(row.get("Brønd 2", "")).strip()

        stik_antal = to_int(row.get("Stik antal"))
        length_m = get_length_m(row)

        item["expected_stik"] += stik_antal
        item["active_stik"] += stik_antal
        item["main_length_m"] += length_m
        item["hovedledning_meter"] += length_m

        if from_brond or to_brond or length_m:
            item["stretches"].append(
                {
                    "from_brond": from_brond,
                    "to_brond": to_brond,
                    "length_m": length_m,
                    "dimension": str(row.get("Ny dim.mm") or row.get("Eks.dim") or "").strip(),
                    "material": str(row.get("Eks.mat") or "").strip(),
                    "stik": stik_antal,
                    "notes": str(row.get("Bemærkninger") or "").strip(),
                }
            )

        item["progress"]["opmaaling"] = min(
            item["progress"]["opmaaling"],
            parse_percent(row.get("Opmål.%")),
        )
        item["progress"]["forarbejde"] = min(
            item["progress"]["forarbejde"],
            parse_percent(row.get("Forarb.%")),
        )
        item["progress"]["stikopmaaling"] = min(
            item["progress"]["stikopmaaling"],
            parse_percent(row.get("Stikopm.%")),
        )
        item["progress"]["hovedledning"] = min(
            item["progress"]["hovedledning"],
            parse_percent(row.get("Inst.%")),
        )
        item["progress"]["stikaabning"] = min(
            item["progress"]["stikaabning"],
            parse_percent(row.get("Stikåbn.")),
        )

        for c5_key, column in [
            ("korthat", "Korthat"),
            ("langhat", "Langhat"),
            ("broendskud", "Brøndskud"),
            ("raaskud", "Råskud"),
            ("pkt_rep", "Pkt.rep"),
        ]:
            value = clean_c5_fraction(row.get(column))
            if value:
                item["c5_values"][c5_key].append(value)

        note = str(row.get("Bemærkninger") or "").strip()
        if note:
            item["notes"].append(note)

    for item in installations.values():
        bronde = set()

        for stretch in item.get("stretches", []):
            if stretch.get("from_brond"):
                bronde.add(stretch["from_brond"])
            if stretch.get("to_brond"):
                bronde.add(stretch["to_brond"])

        item["bronde_total"] = len(bronde)
        item["main_length_m"] = round(item["main_length_m"], 2)
        item["hovedledning_meter"] = round(item["hovedledning_meter"], 2)

    return list(installations.values())


def apply_c5_updates_to_project(project, updates):
    existing = {
        str(item.get("id")): item
        for item in project.get("installations", [])
    }

    for update in updates:
        installation_id = update["id"]

        installation = existing.get(installation_id)

        if not installation:
            installation = {
                "id": installation_id,
                "active": True,
                "hoveddato": None,
                "expected_stik": 0,
                "active_stik": 0,
                "langhatte": 0,
                "korthatte_extra": 0,
                "broende": 0,
                "main_length_m": 0.0,
                "hovedledning_meter": 0.0,
                "bronde_total": 0,
                "stretches": [],
                "notes": "",
            }
            project.setdefault("installations", []).append(
                installation
            )

        installation["expected_stik"] = update["expected_stik"]
        installation["active_stik"] = update["active_stik"]
        installation["main_length_m"] = update.get("main_length_m", 0.0)
        installation["hovedledning_meter"] = update.get("hovedledning_meter", 0.0)
        installation["bronde_total"] = update.get("bronde_total", 0)
        installation["stretches"] = update.get("stretches", [])
        installation["progress"] = update["progress"]

        notes = []

        if update.get("address"):
            notes.append(update["address"])

        if update.get("stretches"):
            stretch_texts = []
            for stretch in update["stretches"]:
                from_brond = stretch.get("from_brond", "")
                to_brond = stretch.get("to_brond", "")
                length_m = stretch.get("length_m", 0)

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

        installation["notes"] = " | ".join(notes)

    return project