from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date


# =========================
# 1. AKTIVITETSTYPER (proces-flow)
# =========================
class Aktivitetstype:
    FORARBEJDE = "forarbejde"
    HOVEDLEDNING = "hovedledning"
    STIK_FORBEREDELSE = "stikforberedelse"
    STIK = "stik"
    KONTROL = "kontrol"
    KORTHAT = "korthat"
    BRØND = "brønd"


# =========================
# 2. FAST PROCESFLOW
# =========================
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
# 3. AKTIVITET (kerneenhed)
# =========================
@dataclass
class Aktivitet:
    id: str
    type: str

    hold: str  # hold-id eller navn (kan senere normaliseres til ID)

    installation_id: str

    varighed_dage: float = 1.0

    afhænger_af: List[str] = field(default_factory=list)

    status: str = "planlagt"

    start_dato: Optional[date] = None
    slut_dato: Optional[date] = None


# =========================
# 4. INSTALLATION (arbejdssektion)
# =========================
@dataclass
class Installation:
    id: str
    projekt_id: str
    rækkefølge: int

    aktiviteter: List[Aktivitet] = field(default_factory=list)


# =========================
# 5. PROJEKT (topniveau)
# =========================
@dataclass
class Projekt:
    id: str
    navn: str

    installationer: List[Installation] = field(default_factory=list)
