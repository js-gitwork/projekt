from datetime import date, timedelta
from typing import List, Dict

REFERENCE_UNITS_PER_DAY = 25


class PlanningEngine:

    def __init__(self, max_installationer_pr_dag=3):
        self.max_installationer_pr_dag = max_installationer_pr_dag


    # =====================================================
    # MAIN ENTRY
    # =====================================================
    def plan(self, installationer: List, startdato: date):
        """
        1. Sortér (simpelt: som modtaget)
        2. Beregn units
        3. Fordel på dage med kapacitet
        """

        schedule = {}
        current_date = startdato

        dagens_inst = []
        dagens_units = 0

        for inst in installationer:

            units = self._calc_units(inst)

            # -----------------------------
            # CAPACITY RULES
            # -----------------------------
            if (len(dagens_inst) >= self.max_installationer_pr_dag) or \
               (dagens_units + units > REFERENCE_UNITS_PER_DAY):

                schedule[current_date] = dagens_inst

                current_date = self._next_day(current_date)

                dagens_inst = []
                dagens_units = 0

            dagens_inst.append(inst)
            dagens_units += units

        # sidste dag
        if dagens_inst:
            schedule[current_date] = dagens_inst

        return schedule


    # =====================================================
    # UNITS MODEL
    # =====================================================
    def _calc_units(self, inst):
        """
        Konverterer installation til produktions-enheder
        """

        units = 0

        # stik
        units += getattr(inst, "antal_stik", 0)

        # brønde
        units += getattr(inst, "antal_brønde", 0) * 10

        # forarbejde overhead (lille men vigtigt)
        units += 2

        return units


    # =====================================================
    # NEXT DAY LOGIC
    # =====================================================
    def _next_day(self, d: date):
        return d + timedelta(days=1)


    # =====================================================
    # OUTPUT
    # =====================================================
    def print_plan(self, schedule: Dict):
        print("\n📅 UNIFIED PLAN")
        print("=" * 50)

        for dag, insts in schedule.items():
            print(f"\n{dag}")
            total = 0

            for i in insts:
                units = self._calc_units(i)
                total += units
                print(f"  - {i.id} ({units} units)")

            print(f"  ➜ TOTAL: {total} units (max {REFERENCE_UNITS_PER_DAY})")
