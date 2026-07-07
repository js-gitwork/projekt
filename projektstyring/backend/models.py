from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date


class Aktivitetstype:
    FORARBEJDE = "forarbejde"
    HOVEDLEDNING = "hovedledning"
    STIK_FORBEREDELSE = "stikforberedelse"
    STIK = "stik"
    KONTROL = "kontrol"
    KORTHAT = "korthat"
    BRØND = "brønd"
    DTVK = "dtvk"


PROCESS_FLOW = [
    Aktivitetstype.FORARBEJDE,
    Aktivitetstype.HOVEDLEDNING,
    Aktivitetstype.STIK_FORBEREDELSE,
    Aktivitetstype.STIK,
    Aktivitetstype.KONTROL,
    Aktivitetstype.KORTHAT,
    Aktivitetstype.BRØND,
    Aktivitetstype.DTVK,
]


@dataclass
class Aktivitet:
    id: str
    installation_id: str
    type: str
    hold: str

    antal_stik: int = 0
    antal_brønde: int = 0
    hovedledning_meter: float = 0.0

    afhænger_af: List[str] = field(default_factory=list)

    start_dato: Optional[date] = None
    slut_dato: Optional[date] = None

    status: str = "planlagt"


@dataclass
class Installation:
    id: str
    projekt_id: str
    rækkefølge: int

    hovedledning_meter: float = 0.0

    aktiviteter: List[Aktivitet] = field(default_factory=list)


@dataclass
class Projekt:
    id: str
    navn: str

    installationer: List[Installation] = field(default_factory=list)