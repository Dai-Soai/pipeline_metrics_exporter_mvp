from pathlib import Path

import pytest

from pipeline_metrics_exporter import (
    ExportArtifact,
    ExportEngine,
    ExportEngineError,
    ExportFormat,
    ExportRequest,
    ObservabilityReportLoader,
    SourceReportType,
)


EXAMPLE_DIRECTORY = Path("examples/input")


def build_request(
    tmp_path: Path,
    *,
    formats: tuple[ExportFormat, ...] = (
        ExportFormat.CSV,
        ExportFormat.MARKDOWN,
        ExportFormat.HTML,
        ExportFormat.EXCEL,
    ),
    overwrite: bool = False,
) -> ExportRequest:
    return ExportRequest(
        source_path=str(
            EXAMPLE_DIRECTORY / "metrics_report.json"
        ),
        source_type=SourceReportType.METRICS,
        formats=formats,
        output_directory=str(tmp_path),
        overwrite=overwrite,
        metadata={
            "requested_by": "test-suite",
        },
    )


class FailingExporter:
    def export(
        self,
        report,
        output_directory,
        *,
        filename=None,
        overwrite=False,
    ):
        raise RuntimeError("simulated exporter failure")


class InvalidArtifactExporter:
    def export(
        self,
        report,
        output_directory,
        *,
        filename=None,
        overwrite=False,
    ):
        return "not-an-artifact"


class WrongFormatExporter:
    def export(
        self,
        report,
        output_directory,
        *,
        filename=None,
        overwrite=False,
    ):
        return ExportArtifact(
            format=ExportFormat.HTML,
            path=str(Path(output_directory) / "wrong.html"),
            size_bytes=10,
            content_type="text/html",
        )


def test_default_engine_supports_all_formats() -> None:
    assert ExportEngine().supported_formats == (
        ExportFormat.CSV,
        ExportFormat.MARKDOWN,
        ExportFormat.HTML,
        ExportFormat.EXCEL,
    )


def test_execute_generates_all_requested_artifacts(
    tmp_path: Path,
) -> None:
    report = ExportEngine().execute(
        build_request(tmp_path)
    )

    assert report.status == "completed"
    assert report.summary.requested_count == 4
    assert report.summary.generated_count == 4
    assert report.summary.failed_count == 0
    assert len(report.artifacts) == 4
    assert report.errors == ()
    assert report.validate() == []

    assert {
        artifact.format
        for artifact in report.artifacts
    } == {
        ExportFormat.CSV,
        ExportFormat.MARKDOWN,
        ExportFormat.HTML,
        ExportFormat.EXCEL,
    }


def test_execute_writes_all_output_files(
    tmp_path: Path,
) -> None:
    report = ExportEngine().execute(
        build_request(tmp_path)
    )

    assert all(
        Path(artifact.path).exists()
        for artifact in report.artifacts
    )


def test_execute_calculates_total_size(
    tmp_path: Path,
) -> None:
    report = ExportEngine().execute(
        build_request(tmp_path)
    )

    assert report.summary.total_size_bytes == sum(
        artifact.size_bytes
        for artifact in report.artifacts
    )


def test_execute_preserves_request_metadata(
    tmp_path: Path,
) -> None:
    report = ExportEngine().execute(
        build_request(tmp_path)
    )

    assert report.request.metadata == {
        "requested_by": "test-suite",
    }


def test_execute_adds_source_metadata(
    tmp_path: Path,
) -> None:
    report = ExportEngine().execute(
        build_request(
            tmp_path,
            formats=(ExportFormat.CSV,),
        )
    )

    assert (
        report.source_metadata["source_type"]
        == "metrics"
    )
    assert (
        report.source_metadata["source_run_id"]
        == "metrics-example-001"
    )
    assert (
        report.source_metadata[
            "source_producer_version"
        ]
        == "0.1.0"
    )
    assert (
        report.source_metadata[
            "source_section_count"
        ]
        == 4
    )


def test_execute_loaded_supports_preloaded_report(
    tmp_path: Path,
) -> None:
    loaded_report = ObservabilityReportLoader().load(
        EXAMPLE_DIRECTORY / "health_report.json"
    )

    request = ExportRequest(
        source_path=str(
            EXAMPLE_DIRECTORY / "health_report.json"
        ),
        source_type=SourceReportType.HEALTH,
        formats=(
            ExportFormat.MARKDOWN,
            ExportFormat.HTML,
        ),
        output_directory=str(tmp_path),
    )

    report = ExportEngine().execute_loaded(
        loaded_report,
        request,
    )

    assert report.status == "completed"
    assert report.summary.generated_count == 2
    assert {
        artifact.format
        for artifact in report.artifacts
    } == {
        ExportFormat.MARKDOWN,
        ExportFormat.HTML,
    }


def test_execute_loaded_rejects_source_type_mismatch(
    tmp_path: Path,
) -> None:
    loaded_report = ObservabilityReportLoader().load(
        EXAMPLE_DIRECTORY / "health_report.json"
    )

    request = ExportRequest(
        source_path=str(
            EXAMPLE_DIRECTORY / "health_report.json"
        ),
        source_type=SourceReportType.METRICS,
        formats=(ExportFormat.CSV,),
        output_directory=str(tmp_path),
    )

    with pytest.raises(
        ExportEngineError,
        match="does not match request source type",
    ):
        ExportEngine().execute_loaded(
            loaded_report,
            request,
        )


def test_engine_reports_partial_status(
    tmp_path: Path,
) -> None:
    engine = ExportEngine(
        exporters={
            ExportFormat.CSV: FailingExporter(),
            ExportFormat.MARKDOWN: (
                __import__(
                    "pipeline_metrics_exporter",
                    fromlist=["MarkdownExporter"],
                ).MarkdownExporter()
            ),
        }
    )

    request = build_request(
        tmp_path,
        formats=(
            ExportFormat.CSV,
            ExportFormat.MARKDOWN,
        ),
    )

    report = engine.execute(request)

    assert report.status == "partial"
    assert report.summary.generated_count == 1
    assert report.summary.failed_count == 1
    assert len(report.errors) == 1
    assert report.errors[0].startswith("csv:")
    assert report.validate() == []


def test_engine_reports_failed_status(
    tmp_path: Path,
) -> None:
    engine = ExportEngine(
        exporters={
            ExportFormat.CSV: FailingExporter(),
        }
    )

    report = engine.execute(
        build_request(
            tmp_path,
            formats=(ExportFormat.CSV,),
        )
    )

    assert report.status == "failed"
    assert report.summary.generated_count == 0
    assert report.summary.failed_count == 1
    assert report.artifacts == ()
    assert len(report.errors) == 1
    assert report.validate() == []


def test_engine_handles_missing_registered_exporter(
    tmp_path: Path,
) -> None:
    engine = ExportEngine(
        exporters={
            ExportFormat.CSV: FailingExporter(),
        }
    )

    request = build_request(
        tmp_path,
        formats=(ExportFormat.HTML,),
    )

    report = engine.execute(request)

    assert report.status == "failed"
    assert report.summary.failed_count == 1
    assert report.errors == (
        "html: no exporter is registered",
    )


def test_engine_rejects_invalid_artifact_result(
    tmp_path: Path,
) -> None:
    engine = ExportEngine(
        exporters={
            ExportFormat.CSV: InvalidArtifactExporter(),
        }
    )

    report = engine.execute(
        build_request(
            tmp_path,
            formats=(ExportFormat.CSV,),
        )
    )

    assert report.status == "failed"
    assert "invalid artifact type" in report.errors[0]


def test_engine_rejects_wrong_artifact_format(
    tmp_path: Path,
) -> None:
    engine = ExportEngine(
        exporters={
            ExportFormat.CSV: WrongFormatExporter(),
        }
    )

    report = engine.execute(
        build_request(
            tmp_path,
            formats=(ExportFormat.CSV,),
        )
    )

    assert report.status == "failed"
    assert "artifact format 'html'" in report.errors[0]


def test_engine_overwrite_request_is_honored(
    tmp_path: Path,
) -> None:
    engine = ExportEngine()

    first = engine.execute(
        build_request(
            tmp_path,
            formats=(ExportFormat.CSV,),
        )
    )

    second = engine.execute(
        build_request(
            tmp_path,
            formats=(ExportFormat.CSV,),
            overwrite=True,
        )
    )

    assert first.status == "completed"
    assert second.status == "completed"
    assert (
        first.artifacts[0].path
        == second.artifacts[0].path
    )
    assert (
        first.artifacts[0].checksum
        == second.artifacts[0].checksum
    )
