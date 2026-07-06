from datetime import date

from projektstyring.backend.project_diagnosis import ProjectDiagnosisBuilder
from projektstyring.backend.multi_schedule_engine import MultiScheduleEngine
from projektstyring.backend.zone_checker import ZoneChecker
from projektstyring.backend.zone_sequence import ZoneSequence
from projektstyring.backend.rest_queue import aggregate_rest_work
from projektstyring.backend.reopen_planner import ReopenPlanner
from projektstyring.backend.reopen_schedule import ReopenScheduleBuilder
from projektstyring.backend.planning_report import PlanningReport
from projektstyring.backend.excel_exporter import ExcelExporter
from projektstyring.backend.resource_report import ResourceReportGenerator
from projektstyring.backend.resource_forecast import ResourceForecastGenerator
from projektstyring.backend.hold_report import HoldReportGenerator
from projektstyring.backend.flow_analyzer import FlowAnalyzer
from projektstyring.backend.project_loader import load_project_installations


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


installationer = load_project_installations(
    "projektstyring/data/projects/V165460_project.json"
)


zone_checker = ZoneChecker(
    "projektstyring/data/projects/V165460_zoner.json"
)

zone_sequence = ZoneSequence(
    "projektstyring/data/projects/V165460_zone_sequence.json",
    zone_checker,
)


engine = MultiScheduleEngine(
    hold_map=hold_map,
    globale_helligdage=globale_helligdage,
    ferieperioder=ferieperioder,
    zone_sequence=zone_sequence,
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


reopen_schedule_builder = ReopenScheduleBuilder(
    globale_helligdage=globale_helligdage,
    ferieperioder=ferieperioder,
)

reopen_schedules = []

for proposal in proposals:
    reopen_schedule = reopen_schedule_builder.build(proposal)
    reopen_schedule.print_summary()
    reopen_schedules.append(reopen_schedule)


report = PlanningReport(
    schedule_result=plan,
    rest_queue=rest_queue,
    reopen_proposals=proposals,
    reopen_schedules=reopen_schedules,
)


hold_generator = HoldReportGenerator()
hold_reports = hold_generator.generate(report)
report.hold_reports = hold_reports

for hold_report in hold_reports:
    hold_report.print_summary()


resource_generator = ResourceReportGenerator(
    hold_map=hold_map,
    globale_helligdage=globale_helligdage,
    ferieperioder=ferieperioder,
)

resource_report = resource_generator.generate(report)
report.resource_report = resource_report
resource_report.print_summary()


forecast_generator = ResourceForecastGenerator()

forecast = forecast_generator.generate(resource_report)
report.resource_forecast = forecast
forecast.print_summary()


flow_analyzer = FlowAnalyzer()

flow_analysis = flow_analyzer.analyze(report)
report.flow_analysis = flow_analysis
flow_analysis.print_summary()


diagnosis_builder = ProjectDiagnosisBuilder()

project_diagnosis = diagnosis_builder.build(report)
report.project_diagnosis = project_diagnosis

print(project_diagnosis.summary)


report.print_summary()


exporter = ExcelExporter()
exporter.export(report, "herslev_plan.xlsx")
