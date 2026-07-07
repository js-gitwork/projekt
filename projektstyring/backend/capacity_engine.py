from math import ceil


class CapacityEngine:
    def __init__(self, hold_map: dict):
        self.hold_map = hold_map

        # baseline produktion
        self.stik_pr_dag = 25

        # DTVK / slutkontrol
        self.dtvk_meter_pr_dag = 700
        self.dtvk_stik_pr_dag = 20

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
        # 1. DTVK / SLUTKONTROL
        # -------------------------------------------------
        if aktivitet.type == "dtvk":
            meter = float(getattr(aktivitet, "hovedledning_meter", 0) or 0)
            stik = int(getattr(aktivitet, "antal_stik", 0) or 0)

            meter_dage = meter / self.dtvk_meter_pr_dag if meter > 0 else 0
            stik_dage = stik / self.dtvk_stik_pr_dag if stik > 0 else 0

            return max(1, ceil(max(meter_dage, stik_dage)))

        # -------------------------------------------------
        # 2. STIK (standard produktion)
        # -------------------------------------------------
        if aktivitet.type == "stik":
            if aktivitet.antal_stik and aktivitet.antal_stik > 0:
                return max(1, ceil(aktivitet.antal_stik / self.stik_pr_dag))
            return 1

        # -------------------------------------------------
        # 3. BRØND (kapacitetsbaseret)
        # -------------------------------------------------
        if aktivitet.type == "brønd":
            if aktivitet.antal_brønde and aktivitet.antal_brønde > 0:
                if kapacitet > 0:
                    return max(1, ceil(aktivitet.antal_brønde / kapacitet))
            return 1

        # -------------------------------------------------
        # 4. HOVEDLEDNING (Filt - manuel styring)
        # -------------------------------------------------
        if rolle == "hovedledning":
            return 1

        # -------------------------------------------------
        # 5. FORARBEJDE (TV6 model - grov estimation)
        # -------------------------------------------------
        if rolle == "forarbejde":
            per_installation = 2.5 / 18
            return max(1, ceil(per_installation))

        # -------------------------------------------------
        # 6. STIKFORBEREDELSE / KONTROL (TV22 type)
        # -------------------------------------------------
        if rolle == "stikforberedelse_kontrol":
            return 1

        # -------------------------------------------------
        # 7. LANGHAT / KORTHAT
        # -------------------------------------------------
        if rolle in ["langhat", "korthat"]:
            return 1

        # -------------------------------------------------
        # 8. FALLBACK (sikkerhed)
        # -------------------------------------------------
        return 1
