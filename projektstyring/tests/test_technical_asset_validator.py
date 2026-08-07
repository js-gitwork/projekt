from decimal import Decimal

from projektstyring.backend.importers.technical_asset_import import (
    ImportedInstallationAssets,
    ImportedManhole,
    ImportedServiceConnection,
    ImportedServiceConnectionWork,
    ImportedStretch,
    TechnicalAssetImport,
)
from projektstyring.backend.importers.technical_asset_validator import (
    TechnicalAssetValidator,
)


def make_valid_import() -> TechnicalAssetImport:
    return TechnicalAssetImport(
        project_id="V165460",
        source="test",
        manholes=[
            ImportedManhole(
                manhole_no="4612022",
                diameter_m=Decimal("1.0"),
                depth_m=Decimal("2.5"),
            ),
            ImportedManhole(
                manhole_no="4612023",
                diameter_m=Decimal("1.0"),
                depth_m=Decimal("2.2"),
            ),
        ],
        installations=[
            ImportedInstallationAssets(
                installation_no="1",
                stretches=[
                    ImportedStretch(
                        sequence=1,
                        bottom_manhole_no="4612022",
                        top_manhole_no="4612023",
                        length_m=Decimal("18.40"),
                        dimension="500",
                        material="PVC",
                        service_connections=[
                            ImportedServiceConnection(
                                external_id=(
                                    "4612022-4612023-18.40-2"
                                ),
                                bottom_manhole_no="4612022",
                                top_manhole_no="4612023",
                                position_m=Decimal("18.40"),
                                clock_position="2",
                                sequence=1,
                                dimension_mm=150,
                                material="PVC",
                            )
                        ],
                    )
                ],
            )
        ],
        service_connection_work=[
            ImportedServiceConnectionWork(
                service_connection_external_id=(
                    "4612022-4612023-18.40-2"
                ),
                work_type="langhat",
                status="completed",
            )
        ],
    )


def test_valid_import_is_accepted():
    validator = TechnicalAssetValidator()

    result = validator.validate(
        make_valid_import()
    )

    assert result.valid is True
    assert result.issues == []


def test_duplicate_manhole_is_rejected():
    import_data = make_valid_import()

    import_data.manholes.append(
        ImportedManhole(
            manhole_no="4612022",
        )
    )

    result = TechnicalAssetValidator().validate(
        import_data
    )

    assert result.valid is False

    assert any(
        issue.code == "duplicate_manhole"
        for issue in result.issues
    )


def test_unknown_manhole_is_rejected():
    import_data = make_valid_import()

    import_data.installations[0].stretches[
        0
    ].top_manhole_no = "9999999"

    result = TechnicalAssetValidator().validate(
        import_data
    )

    assert result.valid is False

    assert any(
        issue.code == "unknown_manhole"
        for issue in result.issues
    )


def test_service_connection_stretch_mismatch_is_rejected():
    import_data = make_valid_import()

    connection = (
        import_data
        .installations[0]
        .stretches[0]
        .service_connections[0]
    )

    connection.top_manhole_no = "9999999"

    result = TechnicalAssetValidator().validate(
        import_data
    )

    assert result.valid is False

    assert any(
        issue.code
        == "service_connection_stretch_mismatch"
        for issue in result.issues
    )


def test_unknown_service_connection_work_is_rejected():
    import_data = make_valid_import()

    import_data.service_connection_work[
        0
    ].service_connection_external_id = (
        "IKKE-EKSISTERENDE-STIK"
    )

    result = TechnicalAssetValidator().validate(
        import_data
    )

    assert result.valid is False

    assert any(
        issue.code
        == "unknown_service_connection_for_work"
        for issue in result.issues
    )


def test_negative_values_are_rejected():
    import_data = make_valid_import()

    import_data.manholes[
        0
    ].depth_m = Decimal("-1")

    import_data.installations[
        0
    ].stretches[
        0
    ].length_m = Decimal("-5")

    connection = (
        import_data
        .installations[0]
        .stretches[0]
        .service_connections[0]
    )

    connection.position_m = Decimal("-2")

    result = TechnicalAssetValidator().validate(
        import_data
    )

    assert result.valid is False

    codes = {
        issue.code
        for issue in result.issues
    }

    assert "invalid_manhole_depth" in codes
    assert "invalid_stretch_length" in codes
    assert (
        "invalid_service_connection_position"
        in codes
    )
