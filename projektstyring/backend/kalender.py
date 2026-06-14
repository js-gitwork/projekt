from datetime import date, timedelta
from typing import List

def beregn_arbejdsdage(
    start_dato: date,
    varighed_dage: float,
    hold: Hold,
    globale_helligdage: List[date]
) -> date:
    """Beregn slutdatoen for en opgave med hensyn til holdets arbejdsdage, ferie og helligdage."""
    arbejdsdage_tæller = 0
    current_dato = start_dato
    target_dage = varighed_dage

    while arbejdsdage_tæller < target_dage:
        if hold.arbejder_paa_dato(current_dato, globale_helligdage):
            arbejdsdage_tæller += 1
        current_dato += timedelta(days=1)

    return current_dato - timedelta(days=1)  # Slutdatoen
