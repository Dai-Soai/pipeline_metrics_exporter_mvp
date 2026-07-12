"""Command-line interface for Pipeline Metrics Exporter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from pipeline_metrics_exporter._version import __version__
from pipeline_metrics_exporter.contract import (
    ExportFormat,
    ExportRequest,
    SourceReportType,
)
from pipeline_metrics_exporter.export_engine import ExportEngine
from pipeline_metrics_exporter.report_io import (
    ExportReportIOError,
    format_export_report_inspection,
    inspect_export_report,
    validate_export_report_file,
    write_export_report,
)


EXIT_SUCCESS = 0
EXIT_PARTIAL = 1
EXIT_FAILURE = 2


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI argument parser."""

    parser = argparse.ArgumentParser(
        prog="pipeline-metrics-exporter",
        description=(
            "Export RADAR_SERVICE metrics, health, and trend "
            "reports to CSV, Markdown, HTML, and Excel."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    export_parser = subparsers.add_parser(
        "export",
        help="Export one observability report.",
    )

    export_parser.add_argument(
        "source",
        help="Path to a metrics, health, or trend JSON report.",
    )

    export_parser.add_argument(
        "--type",
        required=True,
        choices=[
            source_type.value
            for source_type in SourceReportType
        ],
        dest="source_type",
        help="Expected source report type.",
    )

    export_parser.add_argument(
        "--formats",
        default="csv,markdown,html,excel",
        help=(
            "Comma-separated formats: "
            "csv, markdown, html, excel."
        ),
    )

    export_parser.add_argument(
        "--output",
        required=True,
        help="Directory for generated artifacts.",
    )

    export_parser.add_argument(
        "--report-output",
        help=(
            "JSON export-report path. Defaults to "
            "<output>/export_report.json."
        ),
    )

    export_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow existing artifacts and JSON report to be replaced.",
    )

    export_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only the final status.",
    )

    export_parser.add_argument(
        "--metadata",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Attach request metadata. May be supplied multiple times."
        ),
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a generated JSON export report.",
    )

    validate_parser.add_argument(
        "report",
        help="Path to export_report.json.",
    )

    validate_parser.add_argument(
        "--verify-artifacts",
        action="store_true",
        help="Verify generated artifact existence and byte size.",
    )

    validate_parser.add_argument(
        "--verify-checksums",
        action="store_true",
        help="Verify SHA-256 artifact checksums.",
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect a generated JSON export report.",
    )

    inspect_parser.add_argument(
        "report",
        help="Path to export_report.json.",
    )

    inspect_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print inspection as JSON.",
    )

    subparsers.add_parser(
        "version",
        help="Print the installed package version.",
    )

    return parser


def parse_formats(value: str) -> tuple[ExportFormat, ...]:
    """Parse and deduplicate a comma-separated format list."""

    if not isinstance(value, str):
        raise TypeError("formats must be a string")

    raw_values = [
        item.strip().lower()
        for item in value.split(",")
        if item.strip()
    ]

    if not raw_values:
        raise ValueError(
            "at least one export format is required"
        )

    formats: list[ExportFormat] = []

    for raw_value in raw_values:
        try:
            export_format = ExportFormat(raw_value)
        except ValueError as exc:
            supported = ", ".join(
                item.value
                for item in ExportFormat
            )

            raise ValueError(
                f"unsupported export format '{raw_value}'; "
                f"supported formats: {supported}"
            ) from exc

        if export_format in formats:
            raise ValueError(
                f"duplicate export format: {raw_value}"
            )

        formats.append(export_format)

    return tuple(formats)


def parse_metadata(
    values: Sequence[str],
) -> dict[str, str]:
    """Parse repeated KEY=VALUE request metadata arguments."""

    metadata: dict[str, str] = {}

    for value in values:
        key, separator, item_value = value.partition("=")

        key = key.strip()

        if separator != "=" or not key:
            raise ValueError(
                "metadata must use KEY=VALUE syntax"
            )

        if key in metadata:
            raise ValueError(
                f"duplicate metadata key: {key}"
            )

        metadata[key] = item_value

    return metadata


def status_exit_code(status: str) -> int:
    """Map an export status to a process exit code."""

    return {
        "completed": EXIT_SUCCESS,
        "partial": EXIT_PARTIAL,
        "failed": EXIT_FAILURE,
    }.get(status, EXIT_FAILURE)


def command_export(args: argparse.Namespace) -> int:
    """Execute the export subcommand."""

    formats = parse_formats(args.formats)
    metadata = parse_metadata(args.metadata)

    output_directory = Path(args.output).expanduser()

    report_output = (
        Path(args.report_output).expanduser()
        if args.report_output
        else output_directory / "export_report.json"
    )

    request = ExportRequest(
        source_path=str(
            Path(args.source).expanduser()
        ),
        source_type=SourceReportType(
            args.source_type
        ),
        formats=formats,
        output_directory=str(output_directory),
        overwrite=args.overwrite,
        metadata={
            "cli_version": __version__,
            **metadata,
        },
    )

    report = ExportEngine().execute(request)

    written_report = write_export_report(
        report,
        report_output,
        overwrite=args.overwrite,
    )

    if args.quiet:
        print(report.status)
    else:
        print("Pipeline Metrics Export")
        print("=======================")
        print(f"Run ID: {report.run_id}")
        print(f"Status: {report.status}")
        print(
            "Formats requested: "
            + ", ".join(
                export_format.value
                for export_format in request.formats
            )
        )
        print(
            "Artifacts generated: "
            f"{report.summary.generated_count}"
        )
        print(
            "Failed formats: "
            f"{report.summary.failed_count}"
        )
        print(
            "Total size: "
            f"{report.summary.total_size_bytes} bytes"
        )
        print(f"JSON report: {written_report}")

        if report.artifacts:
            print("")
            print("Artifacts:")

            for artifact in report.artifacts:
                print(
                    f"- {artifact.format.value}: "
                    f"{artifact.path} "
                    f"({artifact.size_bytes} bytes)"
                )

        if report.errors:
            print("")
            print("Errors:")

            for error in report.errors:
                print(f"- {error}")

    return status_exit_code(report.status)


def command_validate(args: argparse.Namespace) -> int:
    """Execute the validate subcommand."""

    errors = validate_export_report_file(
        args.report,
        verify_artifacts=args.verify_artifacts,
        verify_checksums=args.verify_checksums,
    )

    if errors:
        print("Export report is invalid.")

        for error in errors:
            print(f"- {error}")

        return EXIT_FAILURE

    print("Export report is valid.")
    return EXIT_SUCCESS


def command_inspect(args: argparse.Namespace) -> int:
    """Execute the inspect subcommand."""

    inspection = inspect_export_report(
        args.report
    )

    if args.as_json:
        print(
            json.dumps(
                inspection,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(
            format_export_report_inspection(
                inspection
            )
        )

    return EXIT_SUCCESS


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Pipeline Metrics Exporter CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "export":
            return command_export(args)

        if args.command == "validate":
            return command_validate(args)

        if args.command == "inspect":
            return command_inspect(args)

        if args.command == "version":
            print(
                f"pipeline-metrics-exporter "
                f"{__version__}"
            )
            return EXIT_SUCCESS

        parser.error(
            f"unsupported command: {args.command}"
        )
    except (
        ExportReportIOError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"error: {exc}",
            file=sys.stderr,
        )

        return EXIT_FAILURE
    except Exception as exc:
        print(
            f"error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

        return EXIT_FAILURE

    return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
