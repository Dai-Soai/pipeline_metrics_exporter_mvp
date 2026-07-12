"""JSON serialization, validation, and inspection for export reports."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from pipeline_metrics_exporter.contract import ExportReport


class ExportReportIOError(Exception):
    """Base exception raised by export report I/O operations."""


class ExportReportFileExistsError(ExportReportIOError):
    """Raised when a report exists and overwrite is disabled."""


class ExportReportJSONError(ExportReportIOError):
    """Raised when an export report contains malformed JSON."""


class ExportReportValidationError(ExportReportIOError):
    """Raised when an export report violates its contract."""

    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def write_export_report(
    report: ExportReport,
    path: str | Path,
    *,
    overwrite: bool = False,
    indent: int = 2,
) -> Path:
    """Serialize an export report to an atomic UTF-8 JSON artifact."""

    if not isinstance(report, ExportReport):
        raise TypeError("report must be an ExportReport")

    if not isinstance(overwrite, bool):
        raise TypeError("overwrite must be a boolean")

    if isinstance(indent, bool) or not isinstance(indent, int):
        raise TypeError("indent must be an integer")

    if indent < 0:
        raise ValueError("indent must not be negative")

    errors = report.validate()

    if errors:
        raise ExportReportValidationError(errors)

    report_path = Path(path).expanduser()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if report_path.exists() and not overwrite:
        raise ExportReportFileExistsError(
            f"Export report already exists: {report_path}"
        )

    content = json.dumps(
        report.to_dict(),
        ensure_ascii=False,
        indent=indent,
        sort_keys=True,
    ) + "\n"

    temporary_path = report_path.with_name(
        f".{report_path.name}.tmp"
    )

    try:
        temporary_path.write_text(
            content,
            encoding="utf-8",
        )

        os.replace(
            temporary_path,
            report_path,
        )
    except OSError as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass

        raise ExportReportIOError(
            f"Unable to write export report {report_path}: {exc}"
        ) from exc

    return report_path.resolve()


def load_export_report(
    path: str | Path,
    *,
    validate: bool = True,
) -> ExportReport:
    """Load an export report from a JSON artifact."""

    if not isinstance(validate, bool):
        raise TypeError("validate must be a boolean")

    report_path = Path(path).expanduser()

    if not report_path.exists():
        raise ExportReportIOError(
            f"Export report not found: {report_path}"
        )

    if not report_path.is_file():
        raise ExportReportIOError(
            f"Export report path is not a file: {report_path}"
        )

    try:
        payload = json.loads(
            report_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ExportReportJSONError(
            f"Invalid JSON in export report {report_path}: "
            f"{exc.msg} at line {exc.lineno}, "
            f"column {exc.colno}"
        ) from exc
    except OSError as exc:
        raise ExportReportIOError(
            f"Unable to read export report {report_path}: {exc}"
        ) from exc

    if not isinstance(payload, Mapping):
        raise ExportReportValidationError(
            ["export report root must be a JSON object"]
        )

    try:
        report = ExportReport.from_dict(payload)
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise ExportReportValidationError(
            [f"unable to deserialize export report: {exc}"]
        ) from exc

    if validate:
        errors = report.validate()

        if errors:
            raise ExportReportValidationError(errors)

    return report


def validate_export_report_file(
    path: str | Path,
    *,
    verify_artifacts: bool = False,
    verify_checksums: bool = False,
) -> list[str]:
    """Return contract and optional artifact verification errors."""

    if not isinstance(verify_artifacts, bool):
        raise TypeError("verify_artifacts must be a boolean")

    if not isinstance(verify_checksums, bool):
        raise TypeError("verify_checksums must be a boolean")

    try:
        report = load_export_report(
            path,
            validate=False,
        )
    except ExportReportIOError as exc:
        return [str(exc)]

    errors = list(report.validate())

    if verify_artifacts or verify_checksums:
        for index, artifact in enumerate(report.artifacts):
            artifact_path = Path(artifact.path).expanduser()

            if not artifact_path.exists():
                errors.append(
                    f"artifacts[{index}] file does not exist: "
                    f"{artifact_path}"
                )
                continue

            if not artifact_path.is_file():
                errors.append(
                    f"artifacts[{index}] path is not a file: "
                    f"{artifact_path}"
                )
                continue

            if verify_artifacts:
                actual_size = artifact_path.stat().st_size

                if actual_size != artifact.size_bytes:
                    errors.append(
                        f"artifacts[{index}] size mismatch: "
                        f"expected {artifact.size_bytes}, "
                        f"actual {actual_size}"
                    )

            if verify_checksums and artifact.checksum:
                algorithm, separator, expected_digest = (
                    artifact.checksum.partition(":")
                )

                if (
                    separator != ":"
                    or algorithm.lower() != "sha256"
                    or not expected_digest
                ):
                    errors.append(
                        f"artifacts[{index}] checksum format "
                        "is unsupported"
                    )
                    continue

                actual_digest = hashlib.sha256(
                    artifact_path.read_bytes()
                ).hexdigest()

                if actual_digest != expected_digest:
                    errors.append(
                        f"artifacts[{index}] checksum mismatch"
                    )

    return errors


def inspect_export_report(
    report_or_path: ExportReport | str | Path,
) -> dict[str, Any]:
    """Return a compact machine-friendly report inspection."""

    if isinstance(report_or_path, ExportReport):
        report = report_or_path
        report_path: str | None = None
    else:
        report = load_export_report(report_or_path)
        report_path = str(
            Path(report_or_path).expanduser().resolve()
        )

    return {
        "report_path": report_path,
        "report_version": report.report_version,
        "exporter_version": report.exporter_version,
        "run_id": report.run_id,
        "generated_at": report.generated_at,
        "status": report.status,
        "source_type": report.request.source_type.value,
        "source_path": report.request.source_path,
        "requested_formats": [
            export_format.value
            for export_format in report.request.formats
        ],
        "requested_count": report.summary.requested_count,
        "generated_count": report.summary.generated_count,
        "failed_count": report.summary.failed_count,
        "total_size_bytes": report.summary.total_size_bytes,
        "artifact_formats": [
            artifact.format.value
            for artifact in report.artifacts
        ],
        "artifact_paths": [
            artifact.path
            for artifact in report.artifacts
        ],
        "error_count": len(report.errors),
        "errors": list(report.errors),
        "source_metadata": dict(report.source_metadata),
    }


def format_export_report_inspection(
    inspection: Mapping[str, Any],
) -> str:
    """Format an export report inspection for terminal output."""

    requested_formats = ", ".join(
        inspection.get("requested_formats", [])
    ) or "none"

    artifact_formats = ", ".join(
        inspection.get("artifact_formats", [])
    ) or "none"

    lines = [
        "Export Report Inspection",
        "========================",
        f"Run ID: {inspection.get('run_id', '')}",
        f"Status: {inspection.get('status', '')}",
        (
            "Report version: "
            f"{inspection.get('report_version', '')}"
        ),
        (
            "Exporter version: "
            f"{inspection.get('exporter_version', '')}"
        ),
        (
            "Generated at: "
            f"{inspection.get('generated_at', '')}"
        ),
        (
            "Source type: "
            f"{inspection.get('source_type', '')}"
        ),
        (
            "Source path: "
            f"{inspection.get('source_path', '')}"
        ),
        f"Requested formats: {requested_formats}",
        (
            "Artifacts generated: "
            f"{inspection.get('generated_count', 0)}"
        ),
        (
            "Failed formats: "
            f"{inspection.get('failed_count', 0)}"
        ),
        (
            "Total size: "
            f"{inspection.get('total_size_bytes', 0)} bytes"
        ),
        f"Artifact formats: {artifact_formats}",
        (
            "Errors: "
            f"{inspection.get('error_count', 0)}"
        ),
    ]

    artifact_paths = inspection.get(
        "artifact_paths",
        [],
    )

    if artifact_paths:
        lines.extend(
            [
                "",
                "Artifacts:",
            ]
        )

        lines.extend(
            f"- {artifact_path}"
            for artifact_path in artifact_paths
        )

    errors = inspection.get("errors", [])

    if errors:
        lines.extend(
            [
                "",
                "Export errors:",
            ]
        )

        lines.extend(
            f"- {error}"
            for error in errors
        )

    return "\n".join(lines)


__all__ = [
    "ExportReportFileExistsError",
    "ExportReportIOError",
    "ExportReportJSONError",
    "ExportReportValidationError",
    "format_export_report_inspection",
    "inspect_export_report",
    "load_export_report",
    "validate_export_report_file",
    "write_export_report",
]
