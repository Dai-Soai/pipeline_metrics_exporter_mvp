import csv
from pathlib import Path

import pytest

from pipeline_metrics_exporter import (
    CSV_COLUMNS,
    CSVExportFileExistsError,
    CSVExporter,
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


def test_build_rows_for_metrics_report() -> None:
    rows = CSVExporter().build_rows(
        load_report(SourceReportType.METRICS)
    )

    assert rows
    assert all(
        row.source_type == "metrics"
        for row in rows
    )
    assert {
        row.section
        for row in rows
    } >= {
        "summary",
        "runtime_metrics",
        "consumer_metrics",
        "latency_metrics",
    }


def test_build_rows_flattens_nested_mapping() -> None:
    rows = CSVExporter().build_rows(
        load_report(SourceReportType.METRICS)
    )

    paths = {
        (row.section, row.path)
        for row in rows
    }

    assert (
        "runtime_metrics",
        "execution_failed",
    ) in paths
    assert (
        "consumer_metrics",
        "acceptance_rate",
    ) in paths


def test_build_rows_flattens_list_items() -> None:
    rows = CSVExporter().build_rows(
        load_report(SourceReportType.HEALTH)
    )

    paths = {
        row.path
        for row in rows
        if row.section == "findings"
    }

    assert "findings[0].code" in paths
    assert "findings[0].severity" in paths


def test_build_rows_supports_trend_report() -> None:
    rows = CSVExporter().build_rows(
        load_report(SourceReportType.TREND)
    )

    paths = {
        row.path
        for row in rows
    }

    assert "samples[0].run_id" in paths
    assert "metric_trends[0].direction" in paths


def test_render_contains_expected_header() -> None:
    content = CSVExporter().render(
        load_report(SourceReportType.METRICS)
    )

    header = content.splitlines()[0]

    assert header == ",".join(CSV_COLUMNS)


def test_render_produces_parseable_csv() -> None:
    content = CSVExporter().render(
        load_report(SourceReportType.HEALTH)
    )

    rows = list(
        csv.DictReader(
            content.splitlines()
        )
    )

    assert rows
    assert set(rows[0]) == set(CSV_COLUMNS)
    assert {
        row["section"]
        for row in rows
    } >= {
        "summary",
        "score",
        "overview",
        "findings",
    }


def test_export_writes_csv_artifact(
    tmp_path: Path,
) -> None:
    artifact = CSVExporter().export(
        load_report(SourceReportType.METRICS),
        tmp_path,
    )

    path = Path(artifact.path)

    assert path.exists()
    assert artifact.format is ExportFormat.CSV
    assert artifact.content_type == "text/csv"
    assert artifact.size_bytes == path.stat().st_size
    assert artifact.checksum is not None
    assert artifact.checksum.startswith("sha256:")
    assert artifact.validate() == []


def test_export_uses_default_filename(
    tmp_path: Path,
) -> None:
    artifact = CSVExporter().export(
        load_report(SourceReportType.METRICS),
        tmp_path,
    )

    assert (
        Path(artifact.path).name
        == "metrics_metrics-example-001.csv"
    )


def test_export_accepts_custom_filename(
    tmp_path: Path,
) -> None:
    artifact = CSVExporter().export(
        load_report(SourceReportType.HEALTH),
        tmp_path,
        filename="Health Export",
    )

    assert Path(artifact.path).name == "Health_Export.csv"


def test_export_creates_parent_directory(
    tmp_path: Path,
) -> None:
    output_directory = (
        tmp_path
        / "nested"
        / "exports"
    )

    artifact = CSVExporter().export(
        load_report(SourceReportType.TREND),
        output_directory,
    )

    assert Path(artifact.path).exists()


def test_export_rejects_existing_file_without_overwrite(
    tmp_path: Path,
) -> None:
    report = load_report(SourceReportType.METRICS)
    exporter = CSVExporter()

    exporter.export(report, tmp_path)

    with pytest.raises(
        CSVExportFileExistsError
    ):
        exporter.export(report, tmp_path)


def test_export_overwrites_existing_file(
    tmp_path: Path,
) -> None:
    report = load_report(SourceReportType.METRICS)
    exporter = CSVExporter()

    first = exporter.export(report, tmp_path)
    second = exporter.export(
        report,
        tmp_path,
        overwrite=True,
    )

    assert first.path == second.path
    assert first.checksum == second.checksum


def test_export_metadata_contains_row_information(
    tmp_path: Path,
) -> None:
    report = load_report(SourceReportType.TREND)

    artifact = CSVExporter().export(
        report,
        tmp_path,
    )

    assert artifact.metadata["source_type"] == "trend"
    assert (
        artifact.metadata["source_run_id"]
        == "trend-example-001"
    )
    assert artifact.metadata["row_count"] > 0
    assert artifact.metadata["section_count"] == 4
    assert artifact.metadata["layout"] == "long-form"


def test_csv_value_types_are_normalized() -> None:
    rows = CSVExporter().build_rows(
        load_report(SourceReportType.METRICS)
    )

    lookup = {
        (row.section, row.path): row
        for row in rows
    }

    assert (
        lookup[
            (
                "runtime_metrics",
                "event_count",
            )
        ].value_type
        == "integer"
    )

    assert (
        lookup[
            (
                "consumer_metrics",
                "acceptance_rate",
            )
        ].value_type
        == "number"
    )
