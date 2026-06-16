from datetime import date
from projektstyring.backend.planning_engine import PlanningEngine


class Inst:
    def __init__(self, id, stik, brønde):
        self.id = id
        self.antal_stik = stik
        self.antal_brønde = brønde


insts = [
    Inst("Inst-3", 20, 1),
    Inst("Inst-5", 30, 0),
    Inst("Inst-7", 15, 2),
    Inst("Inst-4", 40, 1),
    Inst("Inst-6", 10, 0),
]

engine = PlanningEngine(max_installationer_pr_dag=3)

plan = engine.plan(insts, date(2026, 6, 16))

engine.print_plan(plan)
