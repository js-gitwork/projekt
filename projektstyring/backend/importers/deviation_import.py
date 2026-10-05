from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class ImportedDeviation:
    deviation_number: str

    installation_no: str | None = None

    bottom_manhole_no: str | None = None
    top_manhole_no: str | None = None

    dimension_mm: int | None = None

    deviation_type: str = ""
    description: str = ""

    reported_date: date | None = None
    completed_date: date | None = None
    completed_by: str | None = None
    approved_date: date | None = None

    source_reference: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class DeviationImport:
    project_id: str
    source: str

    import_type: str = "deviation_overview"

    deviations: list[
        ImportedDeviation
    ] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )
