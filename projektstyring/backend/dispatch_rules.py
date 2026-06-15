class DispatchRules:
    def __init__(self):
        self.tv22_capacity = 30

        self.thresholds = {
            "lav": 0.75,
            "normal": 0.60,
            "høj": 0.40,
            "kritisk": 0.10,
        }

    def tv22_should_dispatch(
        self,
        stikforberedelse_units: int,
        kontrol_units: int,
        pressure: str = "normal",
        is_final_batch: bool = False
    ):
        total_units = stikforberedelse_units + kontrol_units

        if is_final_batch and total_units > 0:
            return {
                "dispatch": True,
                "reason": "Sidste batch på projektet",
                "total_units": total_units,
                "utilization": total_units / self.tv22_capacity,
            }

        threshold = self.thresholds.get(pressure, self.thresholds["normal"])
        utilization = total_units / self.tv22_capacity

        return {
            "dispatch": utilization >= threshold,
            "reason": self._reason(utilization, threshold, pressure),
            "total_units": total_units,
            "utilization": utilization,
        }

    def _reason(self, utilization, threshold, pressure):
        if utilization >= threshold:
            return f"TV22 sendes ud. Udnyttelse {utilization:.0%}, krav ved '{pressure}' er {threshold:.0%}."
        return f"TV22 venter. Udnyttelse {utilization:.0%}, krav ved '{pressure}' er {threshold:.0%}."
