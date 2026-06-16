from copy import deepcopy
from datetime import timedelta


class OptimizerEngine:

    def __init__(self, reference_capacity=25):
        self.reference_capacity = reference_capacity


    # ==================================================
    # MAIN OPTIMIZE FUNCTION
    # ==================================================
    def optimize(self, schedule, capacity_engine):

        """
        Input:
            schedule = {date: [activities]}
        Output:
            improved schedule
        """

        improved = deepcopy(schedule)

        changed = True
        iteration = 0

        while changed and iteration < 10:
            changed = False
            iteration += 1

            days = sorted(improved.keys())

            for i in range(len(days) - 1):

                day = days[i]
                next_day = days[i + 1]

                current_load = self._calc_load(improved[day], capacity_engine)
                next_load = self._calc_load(improved[next_day], capacity_engine)

                # -----------------------------
                # MOVE WORK IF UNEVEN LOAD
                # -----------------------------
                if current_load < self.reference_capacity * 0.6 and next_load > self.reference_capacity:

                    if len(improved[next_day]) > 1:

                        moved = improved[next_day].pop(0)
                        improved[day].append(moved)

                        changed = True

                # -----------------------------
                # BALANCE OVERLOADED DAY
                # -----------------------------
                elif current_load > self.reference_capacity * 1.2:

                    if len(improved[day]) > 1:

                        moved = improved[day].pop()
                        improved[next_day].insert(0, moved)

                        changed = True

        return improved


    # ==================================================
    # LOAD CALCULATION
    # ==================================================
    def _calc_load(self, activities, capacity_engine):

        total = 0

        for a in activities:
            total += capacity_engine._calc_units(a)

        return total


    # ==================================================
    # DEBUG OUTPUT
    # ==================================================
    def print_plan(self, schedule, capacity_engine):

        print("\n📊 OPTIMIZED PLAN")
        print("=" * 60)

        for day in sorted(schedule.keys()):

            load = self._calc_load(schedule[day], capacity_engine)

            print(f"\n{day} | load: {load}")

            for a in schedule[day]:
                print(f"  - {a.installation_id} | {a.type} | {a.id}")
