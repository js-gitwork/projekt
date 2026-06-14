from datetime import date, timedelta
from typing import List


def er_arbejdsdag(dato: date, hold, helligdage: List[date]) -> bool:
    if dato in helligdage:
        return False

    for ferie in getattr(hold, "ferieperioder", []):
        if ferie.start <= dato <= ferie.slut:
            return False

    weekday_map = {
        0: "man",
        1: "tir",
        2: "ons",
        3: "tor",
        4: "fre",
        5: "lør",
        6: "søn",
    }

    return weekday_map[dato.weekday()] in hold.arbejdsdage


def beregn_slutdato(start: date, varighed: float, hold, helligdage: List[date]) -> date:
    dage = 0
    current = start

    while dage < varighed:
        if er_arbejdsdag(current, hold, helligdage):
            dage += 1
        current += timedelta(days=1)

    return current - timedelta(days=1)
