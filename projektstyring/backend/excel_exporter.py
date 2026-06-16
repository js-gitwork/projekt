from openpyxl import Workbook


class ExcelExporter:
    def export(self, report, filename="plan.xlsx"):
        wb = Workbook()

        # Ark 1: Plan
        ws = wb.active
        ws.title = "Plan"

        ws.append([
            "Installation",
            "Aktivitet",
            "Hold",
            "Start",
            "Slut",
        ])

        for aktivitet in report.schedule_result.activities:
            ws.append([
                aktivitet.installation_id,
                aktivitet.type,
                aktivitet.hold,
                aktivitet.start_dato,
                aktivitet.slut_dato,
            ])

        # Ark 2: Restarbejde
        ws = wb.create_sheet("Restarbejde")

        ws.append([
            "Installation",
            "Aktivitet",
            "Antal",
            "Årsag",
        ])

        for rest in report.schedule_result.rest_work:
            ws.append([
                rest.installation_id,
                rest.task_type,
                rest.quantity,
                rest.reason,
            ])

        # Ark 3: Genåbningsforslag
        ws = wb.create_sheet("Genåbningsforslag")

        ws.append([
            "Zone",
            "Start",
            "Slut",
            "Varighed",
        ])

        for proposal in report.reopen_proposals:
            ws.append([
                proposal.zone,
                proposal.suggested_start,
                proposal.suggested_end,
                proposal.estimated_days_total,
            ])

        # Ark 4: Genåbningsplan
        ws = wb.create_sheet("Genåbningsplan")

        ws.append([
            "Hold",
            "Aktivitet",
            "Start",
            "Slut",
            "Antal",
        ])

        for schedule in report.reopen_schedules:
            for activity in schedule.activities:
                ws.append([
                    activity.hold,
                    activity.task_type,
                    activity.start_dato,
                    activity.slut_dato,
                    activity.quantity,
                ])

        wb.save(filename)

        print(f"\n📄 Excel gemt: {filename}")
