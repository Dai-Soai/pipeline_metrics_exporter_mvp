from pathlib import Path

import pytest

from pipeline_metrics_exporter import (
    ExportFormat,
    MarkdownExportFileExistsError,
    MarkdownExporter,
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


def test_render_metrics_markdown() -> None:
    content = MarkdownExporter().render(
        load_report(SourceReportType.METRICS)
    )

    assert "# Metrics Observability Report" in content
    assert "## Runtime Metrics" in content
    assert "| execution_failed | 1 | integer |" in content


def test_render_health_markdown_preserves_list_paths() -> None:
    content = MarkdownExporter().render(
        load_report(SourceReportType.HEALTH)
    )

    assert "## Findings" in content
    assert "findings[0].code" in content
    assert "findings[0].severity" in content


def test_render_trend_markdown() -> None:
    content = MarkdownExporter().render(
        load_report(SourceReportType.TREND)
    )

    assert "## Samples" in content
    assert "samples[0].run_id" in content
    assert "metric_trends[0].direction" in content


def test_markdown_export_writes_artifact(
    tmp_path: Path,
) -> None:
    artifact = MarkdownExporter().export(
        load_report(SourceReportType.METRICS),
        tmp_path,
    )

    path = Path(artifact.path)

    assert path.exists()
    assert artifact.format is ExportFormat.MARKDOWN
    assert artifact.content_type == "text/markdown"
    assert artifact.size_bytes == path.stat().st_size
    assert artifact.checksum.startswith("sha256:")
    assert artifact.validate() == []


def test_markdown_export_uses_default_filename(
    tmp_path: Path,
) -> None:
    artifact = MarkdownExporter().export(
        load_report(SourceReportType.HEALTH),
        tmp_path,
    )

    assert (
        Path(artifact.path).name
        == "health_health-example-001.md"
    )


def test_markdown_export_rejects_overwrite(
    tmp_path: Path,
) -> None:
    exporter = MarkdownExporter()
    report = load_report(SourceReportType.METRICS)

    exporter.export(report, tmp_path)

    with pytest.raises(
        MarkdownExportFileExistsError
    ):
        exporter.export(report, tmp_path)


def test_markdown_export_allows_explicit_overwrite(
    tmp_path: Path,
) -> None:
    exporter = MarkdownExporter()
    report = load_report(SourceReportType.METRICS)

    first = exporter.export(report, tmp_path)
    second = exporter.export(
        report,
        tmp_path,
        overwrite=True,
    )

    assert first.path == second.path
    assert first.checksum == second.checksum


def test_markdown_escapes_table_separator() -> None:
    report = load_report(SourceReportType.METRICS)
    report.raw_report["custom"] = "alpha|beta"

    assert "\\|" in MarkdownExporter()._escape_cell(
        "alpha|beta"
    )
