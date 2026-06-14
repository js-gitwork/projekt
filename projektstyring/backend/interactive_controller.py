from datetime import date
from typing import List, Dict

from .models import Aktivitet
from .workflow_engine import WorkflowEngine
from .optimizer_engine import OptimizerEngine
from .ai_planner_layer import AIPlannerLayer


class InteractiveController:

    def __init__(self, workflow_engine: WorkflowEngine):

        self.workflow_engine = workflow_engine
        self.optimizer = OptimizerEngine()
        self.ai = AIPlannerLayer()

        self.current_schedule = None


    # ==================================================
    # 1. INITIAL GENERERING
    # ==================================================
    def generate(self, aktiviteter: List[Aktivitet], startdato: date):

        schedule = self.workflow_engine.plan(
            aktiviteter,
            startdato
        )

        schedule = self.optimizer.optimize(
            schedule,
            self.workflow_engine.capacity_engine
        )

        self.current_schedule = schedule

        return schedule


    # ==================================================
    # 2. COMMAND INTERFACE
    # ==================================================
    def command(self, cmd: str, payload: dict):

        if self.current_schedule is None:
            raise Exception("Ingen plan genereret endnu")

        if cmd == "move_activity":

            return self._move_activity(
                payload["activity_id"],
                payload["new_date"]
            )

        elif cmd == "delay_phase":

            return self._delay_phase(
                payload["phase"],
                payload["days"]
            )

        elif cmd == "prioritize_installation":

            return self._prioritize_installation(
                payload["installation_id"]
            )

        elif cmd == "analyze":

            return self.ai.analyze_schedule(self.current_schedule)

        elif cmd == "suggest":

            return self.ai.suggest_improvements(self.current_schedule)

        else:
            raise Exception(f"Ukendt kommando: {cmd}")


    # ==================================================
    # 3. MOVE SINGLE ACTIVITY
    # ==================================================
    def _move_activity(self, activity_id: str, new_date: date):

        for day, activities in self.current_schedule.items():

            for a in activities:

                if a.id == activity_id:

                    activities.remove(a)

                    if new_date not in self.current_schedule:
                        self.current_schedule[new_date] = []

                    self.current_schedule[new_date].append(a)

                    return self._rebuild()

        raise Exception("Activity not found")


    # ==================================================
    # 4. DELAY PHASE
    # ==================================================
    def _delay_phase(self, phase: str, days: int):

        new_schedule = {}

        for day, activities in self.current_schedule.items():

            new_day = day + timedelta(days=days)

            if new_day not in new_schedule:
                new_schedule[new_day] = []

            new_schedule[new_day].extend(activities)

        self.current_schedule = new_schedule

        return self._rebuild()


    # ==================================================
    # 5. PRIORITIZE INSTALLATION
    # ==================================================
    def _prioritize_installation(self, installation_id: str):

        priority = []

        others = []

        for day, activities in self.current_schedule.items():

            for a in activities:

                if a.installation_id == installation_id:
                    priority.append(a)
                else:
                    others.append(a)

        # rebuild schedule with priority first
        self.current_schedule = self._rebuild_from_lists(priority + others)

        return self._rebuild()


    # ==================================================
    # 6. REBUILD PIPELINE
    # ==================================================
    def _rebuild(self):

        all_activities = []

        for activities in self.current_schedule.values():
            all_activities.extend(activities)

        return self.workflow_engine.plan(
            all_activities,
            min(self.current_schedule.keys())
        )


    def _rebuild_from_lists(self, activities):

        return self.workflow_engine.plan(
            activities,
            date.today()
        )
