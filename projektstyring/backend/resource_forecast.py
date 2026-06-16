from dataclasses import dataclass, field


@dataclass
class ResourceForecastItem:
    hold: str
    year: int
    month: int
    utilization: float
    status: str
    recommendation: str


@dataclass
class ResourceForecast:
    items: list[ResourceForecastItem] = field(default_factory=list)

    def print_summary(self):
        print("\n🔮 Ressourceprognose")
        print("-" * 80)

        for item in self.items:
            print(
                f"{item.hold:8} | "
                f"{item.year}-{item.month:02d} | "
                f"{item.utilization:5.1f}% | "
                f"{item.status:12} | "
                f"{item.recommendation}"
            )


class ResourceForecastGenerator:

    def generate(self, resource_report):
        forecast = ResourceForecast()

        for month in resource_report.months:

            utilization = month.utilization_percent

            if utilization >= 90:
                status = "kritisk"
                recommendation = (
                    "Overvej ekstra hold eller flyt arbejde"
                )

            elif utilization >= 75:
                status = "høj"
                recommendation = (
                    "Begrænset ledig kapacitet"
                )

            elif utilization >= 50:
                status = "normal"
                recommendation = (
                    "Kapacitet til mindre ekstraarbejde"
                )

            else:
                status = "lav"
                recommendation = (
                    "Betydelig ledig kapacitet"
                )

            forecast.items.append(
                ResourceForecastItem(
                    hold=month.hold,
                    year=month.year,
                    month=month.month,
                    utilization=utilization,
                    status=status,
                    recommendation=recommendation,
                )
            )

        return forecast
