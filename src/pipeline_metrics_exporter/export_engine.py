"""Unified export engine for RADAR_SERVICE observability artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from pipeline_metrics_exporter._version import __version__
from pipeline_metrics_exporter.contract import (
    ExportArtifact,
    ExportFormat,
    ExportReport,
    ExportRequest,
    ExportSummary,
)
from pipeline_metrics_exporter.csv_exporter import CSVExporter
from pipeline_metrics_exporter.excel_exporter import ExcelExporter
from pipeline_metrics_exporter.html_exporter import HTMLExporter
from pipeline_metrics_exporter.markdown_exporter import MarkdownExporter
from pipeline_metrics_exporter.report_loader import (
    LoadedObservabilityReport,
    ObservabilityReportLoader,
)


EXPORT_REPORT_VERSION = "1.0"


class ExportEngineError(Exception):
    """Base exception raised by the unified export engine."""


class UnsupportedExportFormatError(ExportEngineError):
    """Raised when no exporter is registered for a requested format."""


class ExporterProtocol(Protocol):
    """Minimal exporter interface consumed by ExportEngine."""

    def export(
        self,
        report: LoadedObservabilityReport,
        output_directory: str | Path,
        *,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> ExportArtifact:
        """Export one loaded report."""


class ExportEngine:
    """Execute multi-format observability export requests."""

    def __init__(
        self,
        *,
        loader: ObservabilityReportLoader | None = None,
        exporters: Mapping[
            ExportFormat,
            ExporterProtocol,
        ] | None = None,
    ) -> None:
        self._loader = (
            loader
            if loader is not None
            else ObservabilityReportLoader()
        )

        default_exporters: dict[
            ExportFormat,
            ExporterProtocol,
        ] = {
            ExportFormat.CSV: CSVExporter(),
            ExportFormat.MARKDOWN: MarkdownExporter(),
            ExportFormat.HTML: HTMLExporter(),
            ExportFormat.EXCEL: ExcelExporter(),
        }

        if exporters is None:
            self._exporters = default_exporters
        else:
            self._exporters = dict(exporters)

        self._validate_exporter_registry()

    @property
    def supported_formats(self) -> tuple[ExportFormat, ...]:
        """Return registered export formats in deterministic order."""

        return tuple(
            export_format
            for export_format in ExportFormat
            if export_format in self._exporters
        )

    def execute(
        self,
        request: ExportRequest,
    ) -> ExportReport:
        """Load the request source and execute all requested formats."""

        self._validate_request(request)

        report = self._loader.load(
            request.source_path,
            expected_type=request.source_type,
        )

        return self.execute_loaded(
            report,
            request,
        )

    def execute_loaded(
        self,
        report: LoadedObservabilityReport,
        request: ExportRequest,
    ) -> ExportReport:
        """Execute a request against an already loaded report."""

        self._validate_request(request)
        self._validate_loaded_report(report)

        if report.source_type is not request.source_type:
            raise ExportEngineError(
                "Loaded report source type "
                f"'{report.source_type.value}' does not match "
                f"request source type '{request.source_type.value}'"
            )

        artifacts: list[ExportArtifact] = []
        errors: list[str] = []

        for export_format in request.formats:
            exporter = self._exporters.get(export_format)

            if exporter is None:
                errors.append(
                    f"{export_format.value}: "
                    "no exporter is registered"
                )
                continue

            try:
                artifact = exporter.export(
                    report,
                    request.output_directory,
                    overwrite=request.overwrite,
                )
            except Exception as exc:
                errors.append(
                    f"{export_format.value}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            if not isinstance(artifact, ExportArtifact):
                errors.append(
                    f"{export_format.value}: exporter returned "
                    "an invalid artifact type"
                )
                continue

            if artifact.format is not export_format:
                errors.append(
                    f"{export_format.value}: exporter returned "
                    f"artifact format '{artifact.format.value}'"
                )
                continue

            artifact_errors = artifact.validate()

            if artifact_errors:
                errors.append(
                    f"{export_format.value}: invalid artifact: "
                    + "; ".join(artifact_errors)
                )
                continue

            artifacts.append(artifact)

        status = self._resolve_status(
            generated_count=len(artifacts),
            failed_count=len(errors),
        )

        summary = ExportSummary.from_artifacts(
            requested_count=len(request.formats),
            artifacts=artifacts,
            failed_count=len(errors),
        )

        export_report = ExportReport(
            report_version=EXPORT_REPORT_VERSION,
            exporter_version=__version__,
            run_id=self._generate_run_id(),
            generated_at=self._generated_at(),
            status=status,
            request=request,
            summary=summary,
            artifacts=tuple(artifacts),
            errors=tuple(errors),
            source_metadata={
                "source_type": report.source_type.value,
                "source_report_version": report.report_version,
                "source_producer_version": report.producer_version,
                "source_run_id": report.run_id,
                "source_generated_at": report.generated_at,
                "source_status": report.status,
                "source_path": report.source_path,
                "source_section_count": len(report.sections),
                **dict(report.source_metadata),
            },
        )

        validation_errors = export_report.validate()

        if validation_errors:
            raise ExportEngineError(
                "Generated export report is invalid: "
                + "; ".join(validation_errors)
            )

        return export_report

    def _resolve_status(
        self,
        *,
        generated_count: int,
        failed_count: int,
    ) -> str:
        """Resolve the export execution status."""

        if generated_count > 0 and failed_count == 0:
            return "completed"

        if generated_count > 0 and failed_count > 0:
            return "partial"

        return "failed"

    def _validate_request(
        self,
        request: ExportRequest,
    ) -> None:
        """Validate an export request."""

        if not isinstance(request, ExportRequest):
            raise TypeError(
                "request must be an ExportRequest"
            )

        errors = request.validate()

        if errors:
            raise ValueError("; ".join(errors))

    def _validate_loaded_report(
        self,
        report: LoadedObservabilityReport,
    ) -> None:
        """Validate an already loaded source report."""

        if not isinstance(
            report,
            LoadedObservabilityReport,
        ):
            raise TypeError(
                "report must be a LoadedObservabilityReport"
            )

        errors = report.validate()

        if errors:
            raise ValueError("; ".join(errors))

    def _validate_exporter_registry(self) -> None:
        """Validate registered exporter keys and values."""

        for export_format, exporter in self._exporters.items():
            if not isinstance(export_format, ExportFormat):
                raise TypeError(
                    "exporter registry keys must be ExportFormat values"
                )

            export_method = getattr(
                exporter,
                "export",
                None,
            )

            if not callable(export_method):
                raise TypeError(
                    f"exporter registered for "
                    f"'{export_format.value}' must provide "
                    "a callable export() method"
                )

    def _generate_run_id(self) -> str:
        """Generate a unique export execution identifier."""

        return f"export-{uuid4().hex}"

    def _generated_at(self) -> str:
        """Return the current UTC timestamp."""

        return (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )


__all__ = [
    "EXPORT_REPORT_VERSION",
    "ExportEngine",
    "ExportEngineError",
    "ExporterProtocol",
    "UnsupportedExportFormatError",
]
