import json
from pathlib import Path

import pytest

from pipeline_metrics_exporter import (
    DuplicateObservabilityReportError,
    LoadedObservabilityReport,
    ObservabilityReportFileNotFoundError,
    ObservabilityReportJSONError,
    ObservabilityReportLoader,
    ObservabilityReportValidationError,
    SourceReportType,
    UnsupportedObservabilityReportError,
)


EXAMPLE_DIRECTORY = Path("examples/input")


def test_detects_metrics_report() -> None:
    report = ObservabilityReportLoader().load(
        EXAMPLE_DIRECTORY / "metrics_report.json"
    )

    assert report.source_type is SourceReportType.METRICS
    assert report.producer_version == "0.1.0"
    assert "runtime_metrics" in report.sections


def test_detects_health_report() -> None:
    report = ObservabilityReportLoader().load(
        EXAMPLE_DIRECTORY / "health_report.json"
    )

    assert report.source_type is SourceReportType.HEALTH
    assert report.status == "warning"
    assert "findings" in report.sections


def test_detects_trend_report() -> None:
    report = ObservabilityReportLoader().load(
        EXAMPLE_DIRECTORY / "trend_report.json"
    )

    assert report.source_type is SourceReportType.TREND
    assert "samples" in report.sections
    assert "metric_trends" in report.sections


def test_loaded_report_contract_is_valid() -> None:
    report = ObservabilityReportLoader().load(
        EXAMPLE_DIRECTORY / "metrics_report.json"
    )

    assert isinstance(
        report,
        LoadedObservabilityReport,
    )
    assert report.validate() == []
    assert report.version_metadata == {
        "report_version": "1.0",
        "producer_version": "0.1.0",
    }


def test_loader_preserves_raw_report() -> None:
    path = EXAMPLE_DIRECTORY / "health_report.json"
    expected = json.loads(
        path.read_text(encoding="utf-8")
    )

    report = ObservabilityReportLoader().load(path)

    assert report.raw_report == expected
    assert report.source_path == str(path.resolve())


def test_loader_enforces_expected_type() -> None:
    with pytest.raises(
        ObservabilityReportValidationError
    ) as exc_info:
        ObservabilityReportLoader().load(
            EXAMPLE_DIRECTORY / "health_report.json",
            expected_type=SourceReportType.METRICS,
        )

    assert "does not match expected type" in str(
        exc_info.value
    )


def test_loader_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ObservabilityReportFileNotFoundError
    ):
        ObservabilityReportLoader().load(
            tmp_path / "missing.json"
        )


def test_loader_rejects_invalid_json(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    with pytest.raises(ObservabilityReportJSONError):
        ObservabilityReportLoader().load(path)


def test_loader_rejects_non_object_json() -> None:
    with pytest.raises(
        ObservabilityReportValidationError
    ):
        ObservabilityReportLoader().from_dict(
            ["not", "an", "object"]
        )


def test_loader_rejects_unsupported_report() -> None:
    with pytest.raises(
        UnsupportedObservabilityReportError
    ):
        ObservabilityReportLoader().from_dict(
            {
                "report_version": "1.0",
                "run_id": "unknown",
            }
        )


def test_loader_rejects_missing_required_metadata() -> None:
    data = {
        "collector_version": "0.1.0",
        "runtime_metrics": {
            "event_count": 1,
        },
    }

    with pytest.raises(
        ObservabilityReportValidationError
    ) as exc_info:
        ObservabilityReportLoader().from_dict(data)

    assert (
        "missing required field: report_version"
        in exc_info.value.errors
    )
    assert (
        "missing required field: run_id"
        in exc_info.value.errors
    )


def test_load_directory_loads_all_supported_reports() -> None:
    reports = ObservabilityReportLoader().load_directory(
        EXAMPLE_DIRECTORY
    )

    assert len(reports) == 3
    assert {
        report.source_type
        for report in reports
    } == {
        SourceReportType.METRICS,
        SourceReportType.HEALTH,
        SourceReportType.TREND,
    }


def test_load_directory_can_filter_expected_type(
    tmp_path: Path,
) -> None:
    source = EXAMPLE_DIRECTORY / "metrics_report.json"
    target = tmp_path / "metrics.json"

    target.write_text(
        source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    reports = ObservabilityReportLoader().load_directory(
        tmp_path,
        expected_type=SourceReportType.METRICS,
    )

    assert len(reports) == 1
    assert (
        reports[0].source_type
        is SourceReportType.METRICS
    )


def test_load_many_rejects_duplicate_identity(
    tmp_path: Path,
) -> None:
    source = EXAMPLE_DIRECTORY / "metrics_report.json"
    content = source.read_text(encoding="utf-8")

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    first.write_text(content, encoding="utf-8")
    second.write_text(content, encoding="utf-8")

    with pytest.raises(
        DuplicateObservabilityReportError
    ):
        ObservabilityReportLoader().load_many(
            (first, second)
        )


def test_load_directory_rejects_empty_directory(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ObservabilityReportFileNotFoundError
    ):
        ObservabilityReportLoader().load_directory(
            tmp_path
        )
