from .models import Projekt, Opgave, Hold
from .kalender import beregn_arbejdsdage
from ..core.ai_assistent import ask_mistral

def beregn_projekt_tidsplan(projekt: Projekt) -> Projekt:
    # Sorter opgaver topologisk (afhængigheder først)
    opgaver_sorteret = sorter_opgaver_topologisk(projekt.opgaver)

    for opgave in opgaver_sorteret:
        hold = next(h for h in projekt.hold if h.id == opgave.hold_id)

        # 1. Beregn varighed med AI (hvis ikke sat)
        if opgave.varighed_dage is None:
            prompt = f"""
            Et {opgave.type}-hold med kapacitet {hold.kapacitet_pr_dag} enheder/dag
            skal udføre opgaven: '{opgave.navn}'.
            Hvor mange **arbejdsdage** (ikke kalenderdage) vil dette tage?
            Svaret skal kun være et tal (f.eks. 2.5).
            """
            opgave.varighed_dage = float(ask_mistral(prompt).strip())

        # 2. Beregn startdato (efter afhængigheder)
        if opgave.afhaengigheder:
            # Find seneste slutdato blandt afhængigheder
            seneste_slutdato = max(
                next(o.slut_dato for o in projekt.opgaver if o.id == dep_id)
                for dep_id in opgave.afhaengigheder
            )
            opgave.start_dato = seneste_slutdato + timedelta(days=1)
        else:
            opgave.start_dato = date.today()  # Start i dag

        # 3. Beregn slutdato med kalenderfunktionen
        opgave.slut_dato = beregn_arbejdsdage(
            opgave.start_dato,
            opgave.varighed_dage,
            hold,
            projekt.globale_helligdage
        )

    return projekt

def sorter_opgaver_topologisk(opgaver: List[Opgave]) -> List[Opgave]:
    """Sorter opgaver så afhængigheder kommer før opgaven."""
    # Implementér topologisk sortering (f.eks. med Kahn's algoritme)
    # Foreløbig: Returnér uændret (vi implementerer dette senere)
    return opgaver
