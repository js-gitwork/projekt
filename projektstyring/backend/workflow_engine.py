from datetime import date, timedelta
from typing import List, Dict

from .constraint_engine import ConstraintEngine


WORKFLOW = [
    "forarbejde",
    "hovedledning",
    "stikforberedelse",
    "stik",
    "kontrol",
    "korthat",
    "brønd"
]


class WorkflowEngine:

    def __init__(self, capacity_engine):
        self.capacity_engine = capacity_engine
        self.constraints = ConstraintEngine()


    # ==================================================
    # MAIN ENTRY
    # ==================================================
    def plan(self, aktiviteter: List, startdato: date):

        schedule = {}
        current_date = startdato

        completed_types = set()

        # sortér i korrekt workflow rækkefølge
        aktiviteter = self._sort_by_workflow(aktiviteter)

        for fase in WORKFLOW:

            fase_aktiviteter = [
                a for a in aktiviteter if a.type == fase
            ]

            if not fase_aktiviteter:
                continue

            print(f"\n⚙️ Fase: {fase}")

            # -------------------------------
            # FILTER VIA CONSTRAINTS
            # -------------------------------
            allowed = []

            for a in fase_aktiviteter:

                if self.constraints.can_schedule(a, completed_types):
                    allowed.append(a)
                else:
                    print(
                        self.constraints.explain_block(a, completed_types)
                    )

            if not allowed:
                continue

            # -------------------------------
            # CAPACITY PLAN FOR DENNE FASE
            # -------------------------------
            fase_plan = self.capacity_engine.plan(
                allowed,
                current_date
            )

            # -------------------------------
            # GEM RESULTAT
            # -------------------------------
            for dag, insts in fase_plan.items():

                if dag not in schedule:
                    schedule[dag] = []

                schedule[dag].extend(insts)

            # -------------------------------
            # MARKÉR FASE SOM FÆRDIG
            # -------------------------------
            completed_types.add(fase)

            # næste fase starter efter sidste dag
            current_date = max(fase_plan.keys()) + timedelta(days=1)

        return schedule


    # ==================================================
    # SORTER HJÆLP
    # ==================================================
    def _sort_by_workflow(self, aktiviteter):

        def rank(a):
            return WORKFLOW.index(a.type) if a.type in WORKFLOW else 999

        return sorted(aktiviteter, key=rank)


    # ==================================================
    # OUTPUT
    # ==================================================
    def print_plan(self, schedule):

        print("\n📅 INTEGRATED WORKFLOW PLAN")
        print("=" * 60)

        for dag in sorted(schedule.keys()):

            print(f"\n{dag}")

            for a in schedule[dag]:
                print(f"  - {a.installation_id} | {a.type} | {a.id}")
