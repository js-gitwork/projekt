from datetime import date
from typing import List


class DeadlineChecker:
    def __init__(self, projekt_deadline: date = None):
        self.projekt_deadline = projekt_deadline

    def check_project_deadline(self, aktiviteter: List):
        """
        Tjekker om samlet plan overskrider projektdeadline.
        """

        if not self.projekt_deadline:
            return {
                "status": "OK",
                "message": "Ingen projektdeadline sat.",
                "overskridelse_dage": 0,
                "aktiviteter_efter_deadline": []
            }

        slutdatoer = [
            a.slut_dato for a in aktiviteter
            if a.slut_dato is not None
        ]

        if not slutdatoer:
            return {
                "status": "ADVARSEL",
                "message": "Ingen slutdatoer fundet i planen.",
                "overskridelse_dage": 0,
                "aktiviteter_efter_deadline": []
            }

        samlet_slutdato = max(slutdatoer)

        aktiviteter_efter_deadline = [
            a for a in aktiviteter
            if a.slut_dato and a.slut_dato > self.projekt_deadline
        ]

        if samlet_slutdato <= self.projekt_deadline:
            return {
                "status": "OK",
                "message": f"Planen holder deadline {self.projekt_deadline}.",
                "samlet_slutdato": samlet_slutdato,
                "overskridelse_dage": 0,
                "aktiviteter_efter_deadline": []
            }

        overskridelse = (samlet_slutdato - self.projekt_deadline).days

        return {
            "status": "OVERSKREDET",
            "message": f"Planen slutter {samlet_slutdato}, deadline er {self.projekt_deadline}.",
            "samlet_slutdato": samlet_slutdato,
            "overskridelse_dage": overskridelse,
            "aktiviteter_efter_deadline": aktiviteter_efter_deadline
        }

    def print_result(self, result):
        print("\n⏱ Deadline check")
        print("-" * 80)
        print(result["status"])
        print(result["message"])

        if result.get("overskridelse_dage", 0):
            print(f"Overskridelse: {result['overskridelse_dage']} dage")

        aktiviteter = result.get("aktiviteter_efter_deadline", [])

        if aktiviteter:
            print("\nAktiviteter efter deadline:")
            for a in aktiviteter:
                print(
                    f"{a.slut_dato} | "
                    f"{a.hold:8} | "
                    f"Inst {a.installation_id:8} | "
                    f"{a.type}"
                )
