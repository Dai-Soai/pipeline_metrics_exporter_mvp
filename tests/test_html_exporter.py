from pathlib import Path

import pytest

from pipeline_metrics_exporter import (
    ExportFormat,
    HTMLExportFileExistsError,
    HTMLExporter,
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


def test_render_standalone_html_document() -> None:
    content = HTMLExporter().render(
        load_report(SourceReportType.METRICS)
    )

    assert content.startswith("<!DOCTYPE html>")
    assert "<html lang=\"en\">" in content
    assert "<style>" in content
    assert "Metrics Observability Report" in content
    assert "</html>" in content


def test_render_health_html_preserves_list_paths() -> None:
    content = HTMLExporter().render(
        load_report(SourceReportType.HEALTH)
    )

    assert "findings[0].code" in content
    assert "findings[0].severity" in content


def test_render_trend_html() -> None:
    content = HTMLExporter().render(
        load_report(SourceReportType.TREND)
    )

    assert "samples[0].run_id" in content
    assert "metric_trends[0].direction" in content
    assert "Pipeline health is improving" in content


def test_html_render_escapes_markup() -> None:
    exporter = HTMLExporter()

    assert (
        exporter._metadata_item(
            "Run <ID>",
            "<script>alert(1)</script>",
        )
        == (
            "<div>"
            '<span class="label">Run &lt;ID&gt;</span>'
            "<code>&lt;script&gt;alert(1)"
            "&lt;/script&gt;</code>"
            "</div>"
        )
    )


def test_html_export_writes_artifact(
    tmp_path: Path,
) -> None:
    artifact = HTMLExporter().export(
        load_report(SourceReportType.TREND),
        tmp_path,
    )

    path = Path(artifact.path)

    assert path.exists()
    assert artifact.format is ExportFormat.HTML
    assert artifact.content_type == "text/html"
    assert artifact.size_bytes == path.stat().st_size
    assert artifact.checksum.startswith("sha256:")
    assert artifact.metadata["standalone"] is True
    assert artifact.validate() == []


def test_html_export_uses_custom_filename(
    tmp_path: Path,
) -> None:
    artifact = HTMLExporter().export(
        load_report(SourceReportType.METRICS),
        tmp_path,
        filename="Metrics Dashboard",
    )

    assert (
        Path(artifact.path).name
        == "Metrics_Dashboard.html"
    )


def test_html_export_rejects_overwrite(
    tmp_path: Path,
) -> None:
    exporter = HTMLExporter()
    report = load_report(SourceReportType.HEALTH)

    exporter.export(report, tmp_path)

    with pytest.raises(
        HTMLExportFileExistsError
    ):
        exporter.export(report, tmp_path)


def test_html_export_allows_explicit_overwrite(
    tmp_path: Path,
) -> None:
    exporter = HTMLExporter()
    report = load_report(SourceReportType.HEALTH)

    first = exporter.export(report, tmp_path)
    second = exporter.export(
        report,
        tmp_path,
        overwrite=True,
    )

    assert first.path == second.path
    assert first.checksum == second.checksum
