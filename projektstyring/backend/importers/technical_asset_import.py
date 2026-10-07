from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class ImportedManhole:
    manhole_no: str

    diameter_m: Decimal | None = None
    depth_m: Decimal | None = None
    profile: str = ""
    material: str = ""
    active: bool = True
    notes: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

@dataclass(slots=True)
class ImportedManholeWork:
    manhole_no: str
    work_type: str

    status: str = "planned"
    quantity: Decimal = Decimal("1")
    unit: str = "stk"

    performed_date: date | None = None
    performed_by: str | None = None
    team_id: str | None = None

    source_reference: str | None = None
    notes: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class ImportedServiceConnection:
    external_id: str

    bottom_manhole_no: str
    top_manhole_no: str

    position_m: Decimal
    clock_position: str

    sequence: int = 0
    dimension_mm: int | None = None
    material: str = ""

    active: bool = True
    to_be_opened: bool = False
    decommissioned: bool = False

    notes: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class ImportedServiceConnectionWork:
    service_connection_external_id: str
    work_type: str

    status: str = "planned"
    quantity: Decimal = Decimal("1")
    unit: str = "stk"

    performed_date: date | None = None
    performed_by: str | None = None
    team_id: str | None = None

    source_reference: str | None = None
    notes: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

@dataclass(slots=True)
class ImportedStretchSurvey:
    """
    Tekniske opmålingsdata for ét stræk.

    Opmålingsskemaet er den autoritative kilde.
    A er lodret rørmål.
    B er vandret rørmål.
    """

    existing_profile: str = ""
    existing_dimension: str = ""
    existing_material: str = ""
    existing_length_m: Decimal | None = None

    planned_dimension: str = ""
    planned_length_m: Decimal | None = None

    traffic: str = ""

    bottom_cannot_open: bool = False
    bottom_profile: str = ""
    bottom_dimension_a_mm: Decimal | None = None
    bottom_dimension_b_mm: Decimal | None = None
    bottom_material: str = ""

    top_cannot_open: bool = False
    top_profile: str = ""
    top_dimension_a_mm: Decimal | None = None
    top_dimension_b_mm: Decimal | None = None
    top_material: str = ""

    measured_by: str = ""
    notes: str = ""

    raw_data: dict[str, Any] = field(
        default_factory=dict
    )

@dataclass(slots=True)
class ImportedStretch:
    sequence: int

    bottom_manhole_no: str
    top_manhole_no: str

    length_m: Decimal
    dimension: str = ""
    material: str = ""

    notes: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    survey: ImportedStretchSurvey | None = None

    service_connections: list[
        ImportedServiceConnection
    ] = field(
        default_factory=list
    )

@dataclass(slots=True)
class ImportedInstallationAssets:
    installation_no: str

    stretches: list[
        ImportedStretch
    ] = field(
        default_factory=list
    )

@dataclass(slots=True)
class ImportedProjectConstraint:
    constraint_type: str
    reference: str = ""

    start_date: date | None = None
    end_date: date | None = None

    source: str = ""
    source_reference: str | None = None

    notes: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

@dataclass(slots=True)
class TechnicalAssetImport:
    project_id: str
    source: str
    import_type: str = "generic"

    installations: list[
        ImportedInstallationAssets
    ] = field(
        default_factory=list
    )

    manholes: list[
        ImportedManhole
    ] = field(
        default_factory=list
    )

    manhole_work: list[
        ImportedManholeWork
    ] = field(
        default_factory=list
    )

    service_connection_work: list[
        ImportedServiceConnectionWork
    ] = field(
        default_factory=list
    )

    project_constraints: list[
        ImportedProjectConstraint
    ] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )