from datetime import date

from projektstyring.backend.models import Installation, Aktivitet, Aktivitetstype
from projektstyring.backend.multi_schedule_engine import MultiScheduleEngine
from projektstyring.backend.zone_checker import ZoneChecker
from projektstyring.backend.zone_sequence import ZoneSequence
from projektstyring.backend.rest_queue import aggregate_rest_work
from projektstyring.backend.reopen_planner import ReopenPlanner


class Hold:
    def __init__(self, navn, arbejdsdage, rolle="", kapacitet=0):
        self.navn = navn
        self.arbejdsdage = arbejdsdage
        self.rolle = rolle
        self.kapacitet = kapacitet
        self.ferieperioder = []


hold_map = {
    "FILT": Hold("Filt", ["man", "tir", "ons", "tor", "fre"], rolle="hovedledning"),
    "TV6": Hold("TV6", ["man", "tir", "ons", "tor"], rolle="forarbejde"),
    "TV22": Hold("TV22", ["man", "tir", "ons", "tor"], rolle="stikforberedelse_kontrol", kapacitet=30),
    "STIK2": Hold("Stik2", ["man", "tir", "ons", "tor"], rolle="langhat", kapacitet=5),
    "HAT3": Hold("Hat3", ["man", "tir", "ons", "tor"], rolle="korthat", kapacitet=6),
    "BRØND3": Hold("Brønd3", ["man", "tir", "ons", "tor"], rolle="brøndrenovering", kapacitet=6),
}


globale_helligdage = []

ferieperioder = [
    (date(2026, 7, 13), date(2026, 8, 2))
]


herslev_data = [
    ("2026-06-29", "8", 2),
    ("2026-06-29", "9", 7),
    ("2026-06-30", "2", 7),
    ("2026-06-30", "3", 0),
    ("2026-07-01", "4", 0),
    ("2026-07-01", "5", 6),
    ("2026-07-02", "17", 2),
    ("2026-07-02", "18", 0),
    ("2026-07-03", "10", 1),
    ("2026-07-06", "6", 5),
    ("2026-07-06", "7", 5),
    ("2026-07-07", "11", 0),
    ("2026-07-07", "12", 5),
    ("2026-07-08", "13", 5),
    ("2026-07-08", "14", 1),
    ("2026-07-09", "15", 1),
    ("2026-07-09", "16", 2),
]


def make_installation(hoveddato, inst_id, antal_stik):
    hd = date.fromisoformat(hoveddato)

    inst = Installation(
        id=inst_id,
        projekt_id="V165460",
        rækkefølge=int(inst_id)
    )

    aktiviteter = [
        Aktivitet(
            id=f"{inst_id}_hovedledning",
            installation_id=inst_id,
            type=Aktivitetstype.HOVEDLEDNING,
            hold="FILT",
            start_dato=hd,
            antal_stik=antal_stik,
        ),
        Aktivitet(
            id=f"{inst_id}_stikforberedelse",
            installation_id=inst_id,
            type=Aktivitetstype.STIK_FORBEREDELSE,
            hold="TV22",
            antal_stik=antal_stik,
        ),
        Aktivitet(
            id=f"{inst_id}_stik",
            installation_id=inst_id,
            type=Aktivitetstype.STIK,
            hold="STIK2",
            antal_stik=antal_stik,
        ),
        Aktivitet(
            id=f"{inst_id}_kontrol",
            installation_id=inst_id,
            type=Aktivitetstype.KONTROL,
            hold="TV22",
            antal_stik=antal_stik,
        ),
        Aktivitet(
            id=f"{inst_id}_korthat",
            installation_id=inst_id,
            type=Aktivitetstype.KORTHAT,
            hold="HAT3",
            antal_stik=antal_stik,
        ),
    ]

    inst.aktiviteter = aktiviteter
    return inst


installationer = [
    make_installation(hd, inst, stik)
    for hd, inst, stik in herslev_data
]


zone_checker = ZoneChecker("projektstyring/data/projects/V165460_zoner.json")

zone_sequence = ZoneSequence(
    "projektstyring/data/projects/V165460_zone_sequence.json",
    zone_checker
)


engine = MultiScheduleEngine(
    hold_map=hold_map,
    globale_helligdage=globale_helligdage,
    ferieperioder=ferieperioder,
    zone_sequence=zone_sequence
)


plan = engine.planlæg(installationer)
engine.print_plan(plan)

rest_queue = aggregate_rest_work(plan)
rest_queue.print_summary()

sidste_planlagte_dato = max(
    aktivitet.slut_dato
    for aktivitet in plan.activities
    if aktivitet.slut_dato
)

reopen_planner = ReopenPlanner(
    globale_helligdage=globale_helligdage,
    ferieperioder=ferieperioder,
)

proposals = reopen_planner.create_proposals(
    rest_queue,
    earliest_start=sidste_planlagte_dato,
)

for proposal in proposals:
    proposal.print_summary()
