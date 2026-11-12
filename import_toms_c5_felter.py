
#!/usr/bin/env python3
"""
Import af Toms C5-feltoversigt til Rørbots KnowledgeCatalog.

Kilde:
    Toms oversigt modtaget 12. november 2026.
    Tabel: ETPROKONPOST.

Principper:
    - Tørkørsel som standard.
    - --apply gemmer i én PostgreSQL-transaktion.
    - Eksisterende revisionshistorik bevares.
    - Feltbeskrivelser er kildedokumentation, ikke
      bevis for udført arbejde eller teknisk verificering.
    - Ingen skrivning til C5 eller projektdata.
    - Kan køres igen uden at oprette dubletter.
"""

from __future__ import annotations

import argparse
from collections import Counter

from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.knowledge_service import KnowledgeService
from projektstyring.backend.repositories.knowledge_repository import (
    KnowledgeRepository,
)

SOURCE_KEY = "c5"
TABLE = "ETPROKONPOST"
SOURCE_TITLE = "Toms C5-feltoversigt, 2026-11-12"
SOURCE_SHA256 = (
    "9940fc654ee471e31ac73f0324b4bb00d92e94f3de"
    "73294400fd2d2d3d913a3c"
)

# Format: feltnavn | C5-type | ledetekst | enum-værdier.
# Ledetekster og enum-værdier bevares som angivet af Tom.
# Listen er dokumentation, ikke en AI-genereret fortolkning.

FIELD_DATA = """
PROJNUMBER|STR|Projekt|
REFID|INT|RefID|
LINENUMBER|REAL|Linienr|
STIKNUMMER|STR|Stik-nr.|
ETPROUNDERSXG|ENUM|Undersøg.type|0="", 1=Logisk - Tegning, 2=Afprøvet vand el. lign, 3=Lyd,   4=Kan ikke afprøves, 5=Afproppet, 6=Ender i jord, 7=Stik-TV
TVMXL|REAL|TV-mål|
STIKPLACERINGTOP|REAL|Stikplacering Top|
URREFERENCEBUND|REAL|Ur-reference Bund|
BRXND1AFLXSTMXL|REAL|Brønd 1 aflæst|
BRXND2AFLXSTMXL|REAL|Brønd 2 aflæst|
FACTOR|REAL|+/- faktor|
VURDERING|STR|Vurdering|
GENXBNES|ENUM|Genåbnes|0=Nej, 1=Ja
TILSYNDATO|DATE|Tilsyn dato|
TILSYNSIGNATUR|STR|Tilsyn sign.|
PRIKKETDATO|DATE|Prikket dato|
PRIKKETSIGNATUR|STR|Prikket sign.|
FXRDIGDATO|DATE|Færdig dato|
FXRDIGSIGNATUR|STR|Færdig sign.|
PROUNDERLOGISK|ENUM|Logisk Tegning|0=Nej, 1=Ja
PROUNDERVAND|ENUM|Afprøv.m/vand|0=Nej, 1=Ja
PROUNDERLYD|ENUM|Lyd|0=Nej, 1=Ja
PROUNDERSTIKTV|ENUM|Stik TV|0=Nej, 1=Ja
MXLRETNING|INT|Målt|
STRVXRDI|STR|STR|
PROBESTILTVAND|ENUM|Bestilt.vand|0=Nej, 1=Ja
PROBESTILTTV|ENUM|Bestilt.TV|0=Nej, 1=Ja
KONSTRUKTION|STR|Konstruktion|
AFSTHLSKEL|STR|Afst.HL-Skel|
TVINSPLGD|STR|TV-Insp.Lgd|
TVINSPFRA|STR|TV-Insp.Fra|
TVINSPTIL|STR|TV-Insp.Til|
FORARBEJDETIMER|REAL|Forarb.Timer|
FORARBEJDEINITIAL|STR|Forarb.Init.|
INSTALTIMER|REAL|Inst.Timer|
INSTALINITIAL|STR|Inst.Init.|
RENOVBEM|STR|Renov.bem.|
KONSTGR|ENUM|GR|0=Nej, 1=Ja
KONSTPH|ENUM|PH|0=Nej, 1=Ja
KONSTPVC|ENUM|PVC|0=Nej, 1=Ja
KONSTDIM|STR|Dim.|
STIKKH|ENUM|Kort hat|0=Nej, 1=Ja
STIKLH|ENUM|Lang hat|0=Nej, 1=Ja
STIKST|ENUM|Strømpe|0=Nej, 1=Ja
STIKOM|ENUM|Omega|0=Nej, 1=Ja
GODKEND1|DATE|Godk.LH/LH|
GODKEND2|DATE|Godk.ST/OM|
SPULERRENSTIMER|REAL|SpulerRens Timer|
SPULERRENSINIT|STR|SpulerRens Init.|
SPULERRODTIMER|REAL|SpulerRod Timer|
SPULERRODINIT|STR|SpulerRod Init.|
INSTALTIMER2|REAL|Inst.timer 2|
INSTALINITIAL2|STR|Inst.Init.2|
RENOVLNG|REAL|Renov.længde|
SKELBRXNDFRI|ENUM|Skelbrønd fri|0=Nej, 1=Ja
GODKEND3|DATE|Godkend3|
FORUNDERTVINSP|REAL|Forund.TV|
FORUNDERTIMER|REAL|Forund.Timer|
STIKBRXND|ENUM|Brøndskud|0=Nej, 1=Ja
FORARBEJDEROD|REAL|ForarbejdeRod|
FORARBEJDEHXJTTRYK|REAL|ForarbejdeHøjttryk|
FORARBEJDECUTTER|REAL|ForarbejdeCutter|
STIKDIM|ENUM|Stik-dim.|0="", 1=Ø100, 2=Ø150, 3=Andet
STIKPLACERINGTOPRENOV|REAL|Stik.plac.renov|
URREFERENCEBUNDRENOV|REAL|Ur-ref. bund renov.|
BRXND1AFLXSTMXLRENOV|REAL|Brønd 1 aflæst renov.|
BRXND2AFLXSTMXLRENOV|REAL|Brønd 2 aflæst renov|
PUNKTREPARATION|ENUM|Punkt-rep.|0=Nej, 1=Ja
GODKENDPKT|DATE|Godk.pkt.|
"""


def parse_fields() -> list[dict[str, str]]:
    """Indlæs og validér den dokumenterede feltliste."""
    fields = []

    for line in FIELD_DATA.strip().splitlines():
        parts = line.split("|", 3)

        if len(parts) != 4:
            raise ValueError(f"Ugyldig feltlinje: {line}")

        name, data_type, label, enum_text = parts

        if not name or not label:
            raise ValueError(f"Manglende feltdata: {line}")

        if data_type not in {"STR", "INT", "REAL", "DATE", "ENUM"}:
            raise ValueError(f"Ukendt datatype: {data_type}")

        fields.append({
            "field": name,
            "data_type": data_type,
            "label": label,
            "enum_text": enum_text,
        })

    names = [item["field"] for item in fields]

    if len(fields) != 69 or len(set(names)) != 69:
        raise ValueError(
            "Forventede 69 entydige felter fra Toms oversigt."
        )

    return fields


def build_definition(record: dict[str, str]) -> dict:
    """
    Bevar kildens faktiske oplysninger.

    Ingen automatisk fortolkning af feltets betydning
    eller af om en arbejdsopgave er udført.
    """
    return {
        "table": TABLE,
        "field": record["field"],
        "data_type": record["data_type"],
        "label": record["label"],
        "enum_text": record["enum_text"],
        "documentation_source": SOURCE_TITLE,
        "documentation_sha256": SOURCE_SHA256,
        "documentation_kind": "field_dictionary",
        "note": (
            "Ledetekst fra Tom. Dokumenterer ikke "
            "arbejdsstatus eller yderligere forretningsregler."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Gem ændringerne i PostgreSQL.",
    )
    args = parser.parse_args()

    fields = parse_fields()
    actions = []

    with SessionLocal() as session:
        repository = KnowledgeRepository(session)
        service = KnowledgeService(session)

        source = repository.get_source(SOURCE_KEY)

        if source is None:
            raise RuntimeError(
                "C5-kilden findes ikke i KnowledgeCatalog."
            )

        # Gennemgå alle poster, før vi skriver noget.
        for record in fields:
            field = record["field"]
            key = f"{TABLE}_{field}_field_meaning"

            description = (
                f"C5-felt {TABLE}.{field}: "
                f"ledetekst {record['label']}; "
                f"datatype {record['data_type']}."
            )

            definition = build_definition(record)

            existing = repository.get_entry(
                source_id=source.id,
                knowledge_key=key,
            )

            if existing is None:
                action = "opret"
            else:
                if existing.knowledge_type != "field_meaning":
                    raise RuntimeError(
                        f"Forkert videnskategori: {key}"
                    )

                if existing.verification_status not in {
                    "discovered",
                    "deprecated",
                }:
                    raise RuntimeError(
                        f"{key} har verificeret status "
                        f"{existing.verification_status}. "
                        "Automatisk overskrivning afvist."
                    )

                unchanged = (
                    existing.description == description
                    and existing.definition == definition
                    and existing.verification_status != "deprecated"
                    and existing.schema_fingerprint
                    == source.schema_fingerprint
                )

                action = "uændret" if unchanged else "revider"

            actions.append((
                action,
                key,
                description,
                definition,
            ))

        counts = Counter(item[0] for item in actions)

        print("=== TOMS C5-FELTOVERSIGT ===")
        print("Kilde:", SOURCE_TITLE)
        print("Tabel:", TABLE)
        print("Felter:", len(fields))
        print("Oprettes:", counts["opret"])
        print("Revideres:", counts["revider"])
        print("Uændrede:", counts["uændret"])

        for action, key, _, _ in actions:
            if action == "revider":
                print("REVIDER:", key)

        if not args.apply:
            session.rollback()
            print("\nTØRKØRSEL: Ingen ændringer gemt.")
            return

        # Alle ændringer gemmes i én transaktion.
        # KnowledgeService registrerer revisionshistorikken.
        try:
            for action, key, description, definition in actions:
                if action == "uændret":
                    continue

                service.remember(
                    source_key=SOURCE_KEY,
                    knowledge_key=key,
                    knowledge_type="field_meaning",
                    description=description,
                    definition=definition,
                    actor="tom_field_dictionary_import",
                    reason="Import af Toms C5-feltdokumentation",
                )

            session.commit()

        except Exception:
            session.rollback()
            raise

        print("\nIMPORT FULDFØRT.")
        print("Dokumentationen er gemt i KnowledgeCatalog.")


if __name__ == "__main__":
    main()
