import json
from pathlib import Path

from pipeline_metrics_exporter.cli import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
    main,
    parse_formats,
    parse_metadata,
)
from pipeline_metrics_exporter.contract import ExportFormat


def test_parse_formats() -> None:
    assert parse_formats(
        "csv,markdown,html,excel"
    ) == (
        ExportFormat.CSV,
        ExportFormat.MARKDOWN,
        ExportFormat.HTML,
        ExportFormat.EXCEL,
    )


def test_parse_metadata() -> None:
    assert parse_metadata(
        [
            "milestone=M8",
            "requested_by=test",
        ]
    ) == {
        "milestone": "M8",
        "requested_by": "test",
    }


def test_cli_version(capsys) -> None:
    result = main(["version"])

    captured = capsys.readouterr()

    assert result == EXIT_SUCCESS
    assert (
        "pipeline-metrics-exporter 0.1.0"
        in captured.out
    )


def test_cli_export_generates_artifacts_and_report(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "output"

    result = main(
        [
            "export",
            "examples/input/metrics_report.json",
            "--type",
            "metrics",
            "--formats",
            "csv,markdown,html,excel",
            "--output",
            str(output),
            "--metadata",
            "milestone=M8",
        ]
    )

    captured = capsys.readouterr()

    assert result == EXIT_SUCCESS
    assert "Status: completed" in captured.out
    assert (output / "export_report.json").exists()
    assert len(list(output.glob("*.csv"))) == 1
    assert len(list(output.glob("*.md"))) == 1
    assert len(list(output.glob("*.html"))) == 1
    assert len(list(output.glob("*.xlsx"))) == 1


def test_cli_quiet_mode(
    tmp_path: Path,
    capsys,
) -> None:
    result = main(
        [
            "export",
            "examples/input/health_report.json",
            "--type",
            "health",
            "--formats",
            "markdown",
            "--output",
            str(tmp_path),
            "--quiet",
        ]
    )

    captured = capsys.readouterr()

    assert result == EXIT_SUCCESS
    assert captured.out.strip() == "completed"


def test_cli_validate(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "output"

    export_result = main(
        [
            "export",
            "examples/input/trend_report.json",
            "--type",
            "trend",
            "--formats",
            "csv,excel",
            "--output",
            str(output),
        ]
    )

    assert export_result == EXIT_SUCCESS

    result = main(
        [
            "validate",
            str(output / "export_report.json"),
            "--verify-artifacts",
            "--verify-checksums",
        ]
    )

    captured = capsys.readouterr()

    assert result == EXIT_SUCCESS
    assert "Export report is valid." in captured.out


def test_cli_inspect_json(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "output"

    assert main(
        [
            "export",
            "examples/input/metrics_report.json",
            "--type",
            "metrics",
            "--formats",
            "csv",
            "--output",
            str(output),
        ]
    ) == EXIT_SUCCESS

    capsys.readouterr()

    result = main(
        [
            "inspect",
            str(output / "export_report.json"),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert result == EXIT_SUCCESS
    assert payload["status"] == "completed"
    assert payload["artifact_formats"] == ["csv"]


def test_cli_rejects_invalid_format(
    tmp_path: Path,
    capsys,
) -> None:
    result = main(
        [
            "export",
            "examples/input/metrics_report.json",
            "--type",
            "metrics",
            "--formats",
            "pdf",
            "--output",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()

    assert result == EXIT_FAILURE
    assert (
        "unsupported export format 'pdf'"
        in captured.err
    )
