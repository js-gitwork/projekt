from dataclasses import dataclass, field
from datetime import date


@dataclass
class ProjectInstallationInput:
    id: str
    sequence: int
    expected_stik: int

    hoveddato: date | None = None
    langhatte: int | None = None
    korthatte: int | None = None
    broende: int = 0
    main_length_m: float = 0.0
    notes: str = ""


@dataclass
class ProjectInput:
    id: str
    name: str
    start_date: date
    installations: list[ProjectInstallationInput] = field(default_factory=list)