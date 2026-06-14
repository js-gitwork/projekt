from typing import List


class ConstraintEngine:

    def __init__(self):

        # hårde workflow regler
        self.rules = {
            "hovedledning": [],
            "stikforberedelse": ["hovedledning"],
            "stik": ["stikforberedelse"],
            "kontrol": ["stik"],
            "korthat": ["kontrol"],
            "brønd": ["kontrol"],
        }


    # ======================================
    # CHECK OM AKTIVITET ER GYLDIG
    # ======================================
    def can_schedule(self, aktivitet, completed_types: List[str]) -> bool:
        """
        Tjekker om aktivitet må planlægges
        """

        required = self.rules.get(aktivitet.type, [])

        for req in required:
            if req not in completed_types:
                return False

        return True


    # ======================================
    # SORTER AKTIVITETER KORREKT
    # ======================================
    def sort_activities(self, aktiviteter: List):

        def rank(a):
            return list(self.rules.keys()).index(a.type) if a.type in self.rules else 999

        return sorted(aktiviteter, key=rank)


    # ======================================
    # DEBUG
    # ======================================
    def explain_block(self, aktivitet, completed_types):

        required = self.rules.get(aktivitet.type, [])

        missing = [r for r in required if r not in completed_types]

        if missing:
            return f"❌ Blokeret {aktivitet.type} mangler: {missing}"

        return f"✅ OK {aktivitet.type}"
