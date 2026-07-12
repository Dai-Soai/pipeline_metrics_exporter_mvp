import json
from pathlib import Path

import pytest

from pipeline_metrics_exporter import (
    ExportEngine,
    ExportFormat,
    ExportReportFileExistsError,
    ExportReportJSONError,
    ExportRequest,
    SourceReportType,
    inspect_export_report,
    load_export_report,
    validate_export_report_file,
    write_export_report,
)


def build_report(tmp_path: Path):
    request = ExportRequest(
        source_path="examples/input/metrics_report.json",
        source_type=SourceReportType.METRICS,
        formats=(
            ExportFormat.CSV,
            ExportFormat.MARKDOWN,
        ),
        output_directory=str(tmp_path / "artifacts"),
        overwrite=True,
    )

    return ExportEngine().execute(request)


def test_export_report_json_round_trip(
    tmp_path: Path,
) -> None:
    report = build_report(tmp_path)
    path = tmp_path / "export_report.json"

    write_export_report(report, path)

    restored = load_export_report(path)

    assert restored == report
    assert restored.validate() == []


def test_write_export_report_is_formatted_json(
    tmp_path: Path,
) -> None:
    report = build_report(tmp_path)
    path = tmp_path / "export_report.json"

    write_export_report(report, path)

    content = path.read_text(encoding="utf-8")
    payload = json.loads(content)

    assert content.endswith("\n")
    assert payload["run_id"] == report.run_id
    assert payload["summary"]["generated_count"] == 2


def test_write_export_report_rejects_overwrite(
    tmp_path: Path,
) -> None:
    report = build_report(tmp_path)
    path = tmp_path / "export_report.json"

    write_export_report(report, path)

    with pytest.raises(
        ExportReportFileExistsError
    ):
        write_export_report(report, path)


def test_write_export_report_allows_overwrite(
    tmp_path: Path,
) -> None:
    report = build_report(tmp_path)
    path = tmp_path / "export_report.json"

    first = write_export_report(report, path)
    second = write_export_report(
        report,
        path,
        overwrite=True,
    )

    assert first == second


def test_load_export_report_rejects_invalid_json(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        "{invalid",
        encoding="utf-8",
    )

    with pytest.raises(ExportReportJSONError):
        load_export_report(path)


def test_validate_export_report_file(
    tmp_path: Path,
) -> None:
    report = build_report(tmp_path)
    path = tmp_path / "export_report.json"

    write_export_report(report, path)

    assert validate_export_report_file(path) == []


def test_validate_export_report_verifies_artifacts(
    tmp_path: Path,
) -> None:
    report = build_report(tmp_path)
    path = tmp_path / "export_report.json"

    write_export_report(report, path)

    assert (
        validate_export_report_file(
            path,
            verify_artifacts=True,
            verify_checksums=True,
        )
        == []
    )


def test_inspect_export_report(
    tmp_path: Path,
) -> None:
    report = build_report(tmp_path)
    path = tmp_path / "export_report.json"

    write_export_report(report, path)

    inspection = inspect_export_report(path)

    assert inspection["status"] == "completed"
    assert inspection["source_type"] == "metrics"
    assert inspection["requested_count"] == 2
    assert inspection["generated_count"] == 2
    assert inspection["artifact_formats"] == [
        "csv",
        "markdown",
    ]
