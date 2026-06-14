from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date


# =========================
# 1. WORKFLOW FASER
# =========================
class Aktivitetstype:
    FORARBEJDE = "forarbejde"
    HOVEDLEDNING = "hovedledning"
    STIK_FORBEREDELSE = "stikforberedelse"
    STIK = "stik"
    KONTROL = "kontrol"
    KORTHAT = "korthat"
    BRØND = "brønd"


PROCESS_FLOW = [
    Aktivitetstype.FORARBEJDE,
    Aktivitetstype.HOVEDLEDNING,
    Aktivitetstype.STIK_FORBEREDELSE,
    Aktivitetstype.STIK,
    Aktivitetstype.KONTROL,
    Aktivitetstype.KORTHAT,
    Aktivitetstype.BRØND,
]


# =========================
# 2. AKTIVITET (WORK UNIT BASERET)
# =========================
@dataclass
class Aktivitet:

    id: str
    installation_id: str

    # workflow
    type: str
    hold: str

    # PRODUKTIONSDATA (vigtigt for capacity engine)
    antal_stik: int = 0
    antal_brønde: int = 0

    # afhængigheder (senere workflow engine)
    afhænger_af: List[str] = field(default_factory=list)

    # plan (fyldes af engine)
    start_dato: Optional[date] = None
    slut_dato: Optional[date] = None

    # intern status
    status: str = "planlagt"


# =========================
# 3. INSTALLATION
# =========================
@dataclass
class Installation:

    id: str
    projekt_id: str
    rækkefølge: int

    aktiviteter: List[Aktivitet] = field(default_factory=list)


# =========================
# 4. PROJEKT
# =========================
@dataclass
class Projekt:

    id: str
    navn: str

    installationer: List[Installation] = field(default_factory=list)
