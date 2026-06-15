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
    "FILT": Hold("Filt", ["man", "tir", "ons", "tor", "fre"]),
    "TV6": Hold("TV6", ["man", "tir", "ons", "tor"]),
    "TV22": Hold("TV22", ["man", "tir", "ons", "tor"]),
    "STIK2": Hold("Stik2", ["man", "tir", "ons", "tor"]),
    "HAT3": Hold("Hat3", ["man", "tir", "ons", "tor"]),
    "BRØND3": Hold("Brønd3", ["man", "tir", "ons", "tor"]),
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
engine = ScheduleEngine(
    globale_helligdage=[],
    hold_map=hold_map)

inst = engine.planlæg_installation(
    installation=inst,
    startdato=date(2026, 6, 16),
    hold_map=hold_map
)

# 3. Print resultat
engine.print_schedule(inst)
