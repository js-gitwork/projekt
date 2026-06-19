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


def parse_percent(value):
    return to_int(value, 0)


def clean_c5_fraction(value):
    value = str(value or "").strip()
    value = value.replace("=", "")
    value = value.replace('"', "")
    return value


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

        stik_antal = to_int(row.get("Stik antal"))

        item["expected_stik"] += stik_antal
        item["active_stik"] += stik_antal

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

        from_brond = row.get("Brønd 1", "").strip()
        to_brond = row.get("Brønd 2", "").strip()

        if from_brond or to_brond:
            item["stretches"].append(
                f"{from_brond}-{to_brond}"
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

        note = row.get("Bemærkninger", "").strip()
        if note:
            item["notes"].append(note)

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
                "notes": "",
            }
            project.setdefault("installations", []).append(
                installation
            )

        installation["expected_stik"] = update["expected_stik"]
        installation["active_stik"] = update["active_stik"]
        installation["progress"] = update["progress"]

        notes = []

        if update.get("address"):
            notes.append(update["address"])

        if update.get("stretches"):
            notes.append(
                "Strækninger: "
                + ", ".join(update["stretches"])
            )

        if update.get("notes"):
            notes.append(
                "Bemærkninger: "
                + " | ".join(update["notes"])
            )

        installation["notes"] = " | ".join(notes)

    return project