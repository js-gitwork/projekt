from math import ceil


class CapacityEngine:

    def __init__(self, hold_map: dict):
        self.hold_map = hold_map

        # baseline produktion
        self.stik_pr_dag = 25


    def beregn_varighed(self, aktivitet):
        """
        Returnerer antal dage en aktivitet forventes at tage
        baseret på type, antal og hold-kapacitet.
        """

        hold = self.hold_map.get(aktivitet.hold)

        if not hold:
            raise Exception(f"Ukendt hold: {aktivitet.hold}")

        rolle = getattr(hold, "rolle", "")
        kapacitet = getattr(hold, "kapacitet", 0)

        # -------------------------------------------------
        # 1. STIK (standard produktion)
        # -------------------------------------------------
        if aktivitet.type == "stik":
            if aktivitet.antal_stik and aktivitet.antal_stik > 0:
                return max(1, ceil(aktivitet.antal_stik / self.stik_pr_dag))
            return 1


        # -------------------------------------------------
        # 2. BRØND (kapacitetsbaseret)
        # -------------------------------------------------
        if aktivitet.type == "brønd":
            if aktivitet.antal_brønde and aktivitet.antal_brønde > 0:
                if kapacitet > 0:
                    return max(1, ceil(aktivitet.antal_brønde / kapacitet))
            return 1


        # -------------------------------------------------
        # 3. HOVEDLEDNING (Filt - manuel styring)
        # -------------------------------------------------
        if rolle == "hovedledning":
            # her styrer du selv planlægning senere
            return 1


        # -------------------------------------------------
        # 4. FORARBEJDE (TV6 model - grov estimation)
        # -------------------------------------------------
        if rolle == "forarbejde":
            # 18 installationer ~ 2.5 dage
            per_installation = 2.5 / 18
            return max(1, ceil(per_installation))


        # -------------------------------------------------
        # 5. STIKFORBEREDELSE / KONTROL (TV22 type)
        # -------------------------------------------------
        if rolle == "stikforberedelse_kontrol":
            # typisk 1 dag pr. batch
            return 1


        # -------------------------------------------------
        # 6. LANGHAT / KORTHAT
        # -------------------------------------------------
        if rolle in ["langhat", "korthat"]:
            return 1


        # -------------------------------------------------
        # 7. FALLBACK (sikkerhed)
        # -------------------------------------------------
        return 1
