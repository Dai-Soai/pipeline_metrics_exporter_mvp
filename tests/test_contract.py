from pipeline_metrics_exporter import (
    ExportArtifact,
    ExportFormat,
    ExportReport,
    ExportRequest,
    ExportSummary,
    SourceReportType,
)


def build_request() -> ExportRequest:
    return ExportRequest(
        source_path="examples/input/metrics_report.json",
        source_type=SourceReportType.METRICS,
        formats=(
            ExportFormat.CSV,
            ExportFormat.MARKDOWN,
        ),
        output_directory="examples/output",
        overwrite=False,
        metadata={
            "requested_by": "test-suite",
        },
    )


def build_artifacts() -> tuple[ExportArtifact, ...]:
    return (
        ExportArtifact(
            format=ExportFormat.CSV,
            path="examples/output/metrics_report.csv",
            size_bytes=120,
            content_type="text/csv",
            checksum="sha256:csv-checksum",
        ),
        ExportArtifact(
            format=ExportFormat.MARKDOWN,
            path="examples/output/metrics_report.md",
            size_bytes=240,
            content_type="text/markdown",
            checksum="sha256:markdown-checksum",
        ),
    )


def test_export_format_values() -> None:
    assert ExportFormat.CSV.value == "csv"
    assert ExportFormat.MARKDOWN.value == "markdown"
    assert ExportFormat.HTML.value == "html"
    assert ExportFormat.EXCEL.value == "excel"


def test_source_report_type_values() -> None:
    assert SourceReportType.METRICS.value == "metrics"
    assert SourceReportType.HEALTH.value == "health"
    assert SourceReportType.TREND.value == "trend"


def test_export_request_round_trip() -> None:
    request = build_request()

    restored = ExportRequest.from_dict(
        request.to_dict()
    )

    assert restored == request
    assert restored.validate() == []


def test_export_request_rejects_duplicate_formats() -> None:
    request = ExportRequest(
        source_path="report.json",
        source_type=SourceReportType.METRICS,
        formats=(
            ExportFormat.CSV,
            ExportFormat.CSV,
        ),
        output_directory="output",
    )

    assert (
        "export_request.formats must not contain duplicates"
        in request.validate()
    )


def test_export_artifact_round_trip() -> None:
    artifact = build_artifacts()[0]

    restored = ExportArtifact.from_dict(
        artifact.to_dict()
    )

    assert restored == artifact
    assert restored.filename == "metrics_report.csv"
    assert restored.validate() == []


def test_export_artifact_rejects_negative_size() -> None:
    artifact = ExportArtifact(
        format=ExportFormat.CSV,
        path="output.csv",
        size_bytes=-1,
        content_type="text/csv",
    )

    assert (
        "export_artifact.size_bytes must not be negative"
        in artifact.validate()
    )


def test_export_summary_from_artifacts() -> None:
    artifacts = build_artifacts()

    summary = ExportSummary.from_artifacts(
        requested_count=2,
        artifacts=artifacts,
    )

    assert summary.requested_count == 2
    assert summary.generated_count == 2
    assert summary.failed_count == 0
    assert summary.total_size_bytes == 360
    assert summary.validate() == []


def test_export_summary_rejects_count_mismatch() -> None:
    summary = ExportSummary(
        requested_count=3,
        generated_count=1,
        failed_count=1,
        total_size_bytes=10,
    )

    assert (
        "export_summary.generated_count + failed_count "
        "must equal requested_count"
        in summary.validate()
    )


def test_export_report_round_trip() -> None:
    request = build_request()
    artifacts = build_artifacts()
    summary = ExportSummary.from_artifacts(
        requested_count=2,
        artifacts=artifacts,
    )

    report = ExportReport(
        report_version="1.0",
        exporter_version="0.1.0",
        run_id="export-run-001",
        generated_at="2026-07-12T16:00:00Z",
        status="completed",
        request=request,
        summary=summary,
        artifacts=artifacts,
        source_metadata={
            "source_report_version": "1.0",
        },
    )

    restored = ExportReport.from_dict(
        report.to_dict()
    )

    assert restored == report
    assert restored.validate() == []


def test_export_report_rejects_duplicate_formats() -> None:
    artifact = ExportArtifact(
        format=ExportFormat.CSV,
        path="output/one.csv",
        size_bytes=10,
        content_type="text/csv",
    )

    duplicate_format_artifact = ExportArtifact(
        format=ExportFormat.CSV,
        path="output/two.csv",
        size_bytes=20,
        content_type="text/csv",
    )

    report = ExportReport(
        report_version="1.0",
        exporter_version="0.1.0",
        run_id="export-run-002",
        generated_at="2026-07-12T16:00:00Z",
        status="completed",
        request=ExportRequest(
            source_path="report.json",
            source_type=SourceReportType.METRICS,
            formats=(ExportFormat.CSV,),
            output_directory="output",
        ),
        summary=ExportSummary(
            requested_count=2,
            generated_count=2,
            failed_count=0,
            total_size_bytes=30,
        ),
        artifacts=(
            artifact,
            duplicate_format_artifact,
        ),
    )

    assert (
        "artifacts must not contain duplicate formats"
        in report.validate()
    )


def test_export_report_detects_summary_mismatch() -> None:
    artifact = build_artifacts()[0]

    report = ExportReport(
        report_version="1.0",
        exporter_version="0.1.0",
        run_id="export-run-003",
        generated_at="2026-07-12T16:00:00Z",
        status="completed",
        request=ExportRequest(
            source_path="report.json",
            source_type=SourceReportType.METRICS,
            formats=(ExportFormat.CSV,),
            output_directory="output",
        ),
        summary=ExportSummary(
            requested_count=1,
            generated_count=0,
            failed_count=1,
            total_size_bytes=0,
        ),
        artifacts=(artifact,),
        errors=(),
    )

    errors = report.validate()

    assert (
        "summary.generated_count must match artifacts length"
        in errors
    )
    assert (
        "summary.failed_count must match errors length"
        in errors
    )
    assert (
        "summary.total_size_bytes must match artifact sizes"
        in errors
    )


def test_export_report_validates_required_metadata() -> None:
    report = ExportReport(
        report_version="",
        exporter_version="",
        run_id="",
        generated_at="invalid-date",
        status="",
        request=build_request(),
        summary=ExportSummary(
            requested_count=0,
            generated_count=0,
            failed_count=0,
            total_size_bytes=0,
        ),
        artifacts=(),
    )

    errors = report.validate()

    assert "report_version must not be empty" in errors
    assert "exporter_version must not be empty" in errors
    assert "run_id must not be empty" in errors
    assert "status must not be empty" in errors
    assert (
        "generated_at must be a valid ISO-8601 datetime"
        in errors
    )
