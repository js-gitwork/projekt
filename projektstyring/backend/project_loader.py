import json
from datetime import date

from projektstyring.backend.models import (
    Installation,
    Aktivitet,
    Aktivitetstype,
)


def load_project(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)


def parse_optional_date(value):
    if not value:
        return None

    return date.fromisoformat(value)


def load_project_installations(filename: str) -> list[Installation]:
    project = load_project(filename)

    installations = []

    for default_sequence, item in enumerate(
        project["installations"],
        start=1,
    ):
        expected_stik = item.get("expected_stik", 0)

        langhatte = item.get("langhatte")
        korthatte = item.get("korthatte")

        if langhatte is None:
            langhatte = expected_stik

        if korthatte is None:
            korthatte = langhatte

        inst = make_installation(
            project_id=project["id"],
            inst_id=item["id"],
            sequence=item.get("sequence", default_sequence),
            hoveddato=item.get("hoveddato"),
            expected_stik=expected_stik,
            langhatte=langhatte,
            korthatte=korthatte,
            broende=item.get("broende", 0),
        )

        installations.append(inst)

    return installations


def make_installation(
    project_id: str,
    inst_id: str,
    sequence: int,
    hoveddato: str | None,
    expected_stik: int,
    langhatte: int,
    korthatte: int,
    broende: int = 0,
) -> Installation:
    hd = parse_optional_date(hoveddato)

    inst = Installation(
        id=inst_id,
        projekt_id=project_id,
        rækkefølge=sequence,
    )

    inst.aktiviteter = [
        Aktivitet(
            id=f"{inst_id}_hovedledning",
            installation_id=inst_id,
            type=Aktivitetstype.HOVEDLEDNING,
            hold="FILT",
            start_dato=hd,
            antal_stik=expected_stik,
            antal_brønde=broende,
        ),
        Aktivitet(
            id=f"{inst_id}_stikforberedelse",
            installation_id=inst_id,
            type=Aktivitetstype.STIK_FORBEREDELSE,
            hold="TV22",
            antal_stik=expected_stik,
        ),
        Aktivitet(
            id=f"{inst_id}_stik",
            installation_id=inst_id,
            type=Aktivitetstype.STIK,
            hold="STIK2",
            antal_stik=langhatte,
        ),
        Aktivitet(
            id=f"{inst_id}_kontrol",
            installation_id=inst_id,
            type=Aktivitetstype.KONTROL,
            hold="TV22",
            antal_stik=expected_stik,
        ),
        Aktivitet(
            id=f"{inst_id}_korthat",
            installation_id=inst_id,
            type=Aktivitetstype.KORTHAT,
            hold="HAT3",
            antal_stik=korthatte,
        ),
    ]

    return inst
