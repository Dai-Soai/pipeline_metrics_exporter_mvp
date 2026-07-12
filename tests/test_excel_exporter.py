from pathlib import Path
from zipfile import ZipFile

import pytest

from pipeline_metrics_exporter import (
    EXCEL_CONTENT_TYPE,
    ExcelExportFileExistsError,
    ExcelExporter,
    ExportFormat,
    ObservabilityReportLoader,
    SourceReportType,
)


EXAMPLE_DIRECTORY = Path("examples/input")


def load_report(source_type: SourceReportType):
    filename = {
        SourceReportType.METRICS: "metrics_report.json",
        SourceReportType.HEALTH: "health_report.json",
        SourceReportType.TREND: "trend_report.json",
    }[source_type]

    return ObservabilityReportLoader().load(
        EXAMPLE_DIRECTORY / filename
    )


def test_build_sheets_for_metrics_report() -> None:
    sheets = ExcelExporter().build_sheets(
        load_report(SourceReportType.METRICS)
    )

    names = {
        sheet.name
        for sheet in sheets
    }

    assert "Metadata" in names
    assert "Summary" in names
    assert "Runtime Metrics" in names
    assert "Consumer Metrics" in names
    assert "Latency Metrics" in names
    assert "Source Metadata" in names


def test_build_sheets_for_health_report() -> None:
    sheets = ExcelExporter().build_sheets(
        load_report(SourceReportType.HEALTH)
    )

    names = {
        sheet.name
        for sheet in sheets
    }

    assert "Score" in names
    assert "Overview" in names
    assert "Findings" in names


def test_build_sheets_preserves_array_paths() -> None:
    sheets = ExcelExporter().build_sheets(
        load_report(SourceReportType.TREND)
    )

    samples_sheet = next(
        sheet
        for sheet in sheets
        if sheet.name == "Samples"
    )

    metric_trends_sheet = next(
        sheet
        for sheet in sheets
        if sheet.name == "Metric Trends"
    )

    sample_paths = {
        row[0]
        for row in samples_sheet.rows[1:]
    }

    metric_paths = {
        row[0]
        for row in metric_trends_sheet.rows[1:]
    }

    assert "samples[0].run_id" in sample_paths
    assert "samples[0].health_score" in sample_paths
    assert "metric_trends[0].direction" in metric_paths


def test_sheet_names_are_valid_and_unique() -> None:
    exporter = ExcelExporter()
    used_names: set[str] = set()

    first = exporter._unique_sheet_name(
        "Invalid:/Name*?",
        used_names,
    )

    second = exporter._unique_sheet_name(
        "Invalid:/Name*?",
        used_names,
    )

    long_name = exporter._unique_sheet_name(
        "A" * 100,
        used_names,
    )

    assert first == "Invalid__Name__"
    assert second == "Invalid__Name__ 2"
    assert len(long_name) == 31
    assert all(
        character not in first
        for character in "[]:*?/\\"
    )


def test_column_name_conversion() -> None:
    exporter = ExcelExporter()

    assert exporter._column_name(1) == "A"
    assert exporter._column_name(26) == "Z"
    assert exporter._column_name(27) == "AA"
    assert exporter._column_name(52) == "AZ"
    assert exporter._column_name(53) == "BA"


def test_excel_export_writes_artifact(
    tmp_path: Path,
) -> None:
    artifact = ExcelExporter().export(
        load_report(SourceReportType.METRICS),
        tmp_path,
    )

    path = Path(artifact.path)

    assert path.exists()
    assert artifact.format is ExportFormat.EXCEL
    assert artifact.content_type == EXCEL_CONTENT_TYPE
    assert artifact.size_bytes == path.stat().st_size
    assert artifact.checksum.startswith("sha256:")
    assert artifact.metadata["workbook_format"] == "xlsx"
    assert artifact.metadata["sheet_count"] >= 2
    assert artifact.validate() == []


def test_excel_export_uses_default_filename(
    tmp_path: Path,
) -> None:
    artifact = ExcelExporter().export(
        load_report(SourceReportType.HEALTH),
        tmp_path,
    )

    assert (
        Path(artifact.path).name
        == "health_health-example-001.xlsx"
    )


def test_excel_export_accepts_custom_filename(
    tmp_path: Path,
) -> None:
    artifact = ExcelExporter().export(
        load_report(SourceReportType.TREND),
        tmp_path,
        filename="Trend Workbook",
    )

    assert (
        Path(artifact.path).name
        == "Trend_Workbook.xlsx"
    )


def test_excel_export_rejects_existing_file(
    tmp_path: Path,
) -> None:
    exporter = ExcelExporter()
    report = load_report(SourceReportType.METRICS)

    exporter.export(report, tmp_path)

    with pytest.raises(
        ExcelExportFileExistsError
    ):
        exporter.export(report, tmp_path)


def test_excel_export_allows_explicit_overwrite(
    tmp_path: Path,
) -> None:
    exporter = ExcelExporter()
    report = load_report(SourceReportType.METRICS)

    first = exporter.export(report, tmp_path)
    second = exporter.export(
        report,
        tmp_path,
        overwrite=True,
    )

    assert first.path == second.path
    assert first.checksum == second.checksum


def test_generated_workbook_contains_required_parts(
    tmp_path: Path,
) -> None:
    artifact = ExcelExporter().export(
        load_report(SourceReportType.TREND),
        tmp_path,
    )

    inspection = ExcelExporter().inspect_workbook(
        artifact.path
    )

    assert inspection["valid_zip"] is True
    assert inspection["missing_required_entries"] == []
    assert inspection["has_styles"] is True
    assert inspection["has_workbook"] is True
    assert (
        inspection["worksheet_count"]
        == artifact.metadata["sheet_count"]
    )


def test_generated_workbook_contains_sheet_names(
    tmp_path: Path,
) -> None:
    artifact = ExcelExporter().export(
        load_report(SourceReportType.TREND),
        tmp_path,
    )

    inspection = ExcelExporter().inspect_workbook(
        artifact.path
    )

    workbook_xml = inspection["workbook_xml"]

    assert 'name="Metadata"' in workbook_xml
    assert 'name="Summary"' in workbook_xml
    assert 'name="Samples"' in workbook_xml
    assert 'name="Metric Trends"' in workbook_xml


def test_generated_workbook_is_valid_zip_package(
    tmp_path: Path,
) -> None:
    artifact = ExcelExporter().export(
        load_report(SourceReportType.HEALTH),
        tmp_path,
    )

    with ZipFile(artifact.path) as archive:
        assert archive.testzip() is None
        assert "[Content_Types].xml" in archive.namelist()
        assert "xl/styles.xml" in archive.namelist()
        assert "xl/worksheets/sheet1.xml" in archive.namelist()
