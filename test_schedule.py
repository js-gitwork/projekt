from datetime import date

from projektstyring.backend.models import Installation
from projektstyring.backend.planner import generer_aktiviteter
from projektstyring.backend.schedule_engine import ScheduleEngine


# -------------------------
# SIMPLE HOLD MODEL (test)
# -------------------------
class Hold:
    def __init__(self, navn, arbejdsdage):
        self.navn = navn
        self.arbejdsdage = arbejdsdage
        self.ferieperioder = []


# -------------------------
# HOLD MAP
# -------------------------
hold_map = {
    "tv_cutter": Hold("TV Cutter", ["man", "tir", "ons", "tor", "fre"]),
    "hoved_stramforing": Hold("Hovedledning", ["man", "tir", "ons", "tor", "fre"]),
    "tv_stik": Hold("Stik TV", ["man", "tir", "ons", "tor", "fre"]),
    "langhat": Hold("Langhat", ["man", "tir", "ons", "tor", "fre"]),
    "tv_kontrol": Hold("Kontrol TV", ["man", "tir", "ons", "tor", "fre"]),
    "korthat_hold": Hold("Korthat", ["man", "tir", "ons", "tor", "fre"]),
    "brøndhold": Hold("Brønd", ["man", "tir", "ons", "tor", "fre"]),
}


# -------------------------
# INSTALLATION TEST
# -------------------------
inst = Installation(
    id="INST-001",
    projekt_id="P-100",
    rækkefølge=1
)

# 1. Generér proces (fra planner)
inst = generer_aktiviteter(inst)

# 2. Schedule engine
engine = ScheduleEngine(globale_helligdage=[])

inst = engine.planlæg_installation(
    installation=inst,
    startdato=date(2026, 6, 16),
    hold_map=hold_map
)

# 3. Print resultat
engine.print_schedule(inst)
