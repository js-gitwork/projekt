from dataclasses import dataclass, field


@dataclass
class ProjectDiagnosis:
    status: str
    problems: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    summary: str = ""


class ProjectDiagnosisBuilder:
    def build(self, report) -> ProjectDiagnosis:
        problems = []
        recommendations = []

        # Restarbejde
        if report.rest_queue:
            total_stik = report.rest_queue.total_stik()
            total_broende = report.rest_queue.total_brønde()

            if total_stik > 0:
                problems.append(f"{total_stik} stik i restkø")

            if total_broende > 0:
                problems.append(f"{total_broende} brønde i restkø")

        # Warnings
        for warning in report.schedule_result.warnings:
            problems.append(str(warning))

        # Flowanalyse
        if report.flow_analysis:
            for gap in getattr(report.flow_analysis, "gaps", []):
                problems.append(
                    f"Ventetid {gap.waiting_days} dage: "
                    f"Inst {gap.installation_id} "
                    f"{gap.from_task} → {gap.to_task}"
                )

            for break_item in getattr(report.flow_analysis, "breaks", []):
                problems.append(
                    f"Flowbrud: Inst {break_item.installation_id} "
                    f"{break_item.task_type} - {break_item.reason}"
                )

        # Ressourceprognose
        if report.resource_forecast:
            for item in getattr(report.resource_forecast, "items", []):
                level = getattr(item, "level", "")
                hold = getattr(item, "hold", "")

                if level in ["Høj", "Kritisk"]:
                    problems.append(
                        f"{hold} har {level.lower()} belastning"
                    )

                if level == "Lav":
                    recommendations.append(
                        f"{hold} har mulig ledig kapacitet"
                    )

        # Genåbningsforslag
        if report.reopen_proposals:
            recommendations.append(
                "Vurder genåbning af zone for at færdiggøre restarbejde"
            )

        # Statusvurdering
        problem_texts = [str(problem) for problem in problems]

        if any(
            "kritisk" in problem.lower()
            or "manglende" in problem.lower()
            or "flowbrud" in problem.lower()
            for problem in problem_texts
        ):
            status = "Rød"
        elif problems:
            status = "Gul"
        else:
            status = "Grøn"

        summary = self._build_summary(
            status,
            problems,
            recommendations,
        )

        return ProjectDiagnosis(
            status=status,
            problems=problems,
            recommendations=recommendations,
            summary=summary,
        )

    def _build_summary(
        self,
        status,
        problems,
        recommendations,
    ):
        lines = []

        lines.append("📋 Projektdiagnose")
        lines.append("")
        lines.append(f"Status: {status}")
        lines.append("")

        if problems:
            lines.append("Problemer:")

            for problem in problems:
                lines.append(f"- {problem}")

            lines.append("")

        if recommendations:
            lines.append("Anbefalinger:")

            for recommendation in recommendations:
                lines.append(f"- {recommendation}")

        if not problems and not recommendations:
            lines.append(
                "Ingen væsentlige problemer fundet."
            )

        return "\n".join(lines)
