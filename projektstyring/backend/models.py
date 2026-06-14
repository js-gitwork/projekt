from pydantic import BaseModel
from typing import List, Optional
from datetime import date, timedelta
import json

class FeriePeriode(BaseModel):
    start: date      # f.eks. date(2026, 7, 13)
    slut: date       # f.eks. date(2026, 8, 3)
    beskrivelse: str = "Ferie"

class Hold(BaseModel):
    id: int
    navn: str
    kapacitet_pr_dag: float  # f.eks. 30 (TV-hold)
    arbejdsdage: List[str] = ["man", "tir", "ons", "tor", "fre"]  # Mulige: ["man", "tir", "ons", "tor", "fre", "lør", "søn"]
    daglig_arbejdstid: float = 8.0  # Timer pr. dag (f.eks. 7.5 for tidlig fri)
    ferieperioder: List[FeriePeriode] = []
    specifikke_helligdage: List[date] = []  # Hold-specifikke helligdage

    def arbejder_paa_dato(self, dato: date, globale_helligdage: List[date]) -> bool:
        """Check om holdet arbejder på en given dato"""
        # 1. Check globale + specifikke helligdage
        if dato in globale_helligdage or dato in self.specifikke_helligdage:
            return False
        # 2. Check ferieperioder
        for ferie in self.ferieperioder:
            if ferie.start <= dato <= ferie.slut:
                return False
        # 3. Check ugedag
        ugedag = dato.strftime("%a").lower()  # "mon", "tue", etc.
        da_til_en = {"man": "mon", "tir": "tue", "ons": "wed", "tor": "thu", "fre": "fri", "lør": "sat", "søn": "sun"}
        return da_til_en.get(ugedag, ugedag) in [da_til_en[d] for d in self.arbejdsdage]
