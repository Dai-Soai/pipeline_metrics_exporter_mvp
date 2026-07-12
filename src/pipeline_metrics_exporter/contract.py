"""Core contracts for Pipeline Metrics Exporter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence


class ExportFormat(str, Enum):
    """Supported export artifact formats."""

    CSV = "csv"
    MARKDOWN = "markdown"
    HTML = "html"
    EXCEL = "excel"


class SourceReportType(str, Enum):
    """Supported RADAR_SERVICE observability report types."""

    METRICS = "metrics"
    HEALTH = "health"
    TREND = "trend"


@dataclass(frozen=True, slots=True)
class ExportRequest:
    """Request describing how one source report should be exported."""

    source_path: str
    source_type: SourceReportType
    formats: tuple[ExportFormat, ...]
    output_directory: str
    overwrite: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Return validation errors for this export request."""

        errors: list[str] = []

        if not isinstance(self.source_path, str):
            errors.append("export_request.source_path must be a string")
        elif not self.source_path.strip():
            errors.append("export_request.source_path must not be empty")

        if not isinstance(self.source_type, SourceReportType):
            errors.append(
                "export_request.source_type must be a SourceReportType"
            )

        if not isinstance(self.formats, tuple):
            errors.append("export_request.formats must be a tuple")
        elif not self.formats:
            errors.append("export_request.formats must not be empty")
        else:
            seen_formats: set[ExportFormat] = set()

            for index, export_format in enumerate(self.formats):
                if not isinstance(export_format, ExportFormat):
                    errors.append(
                        f"export_request.formats[{index}] "
                        "must be an ExportFormat"
                    )
                    continue

                if export_format in seen_formats:
                    errors.append(
                        "export_request.formats must not contain duplicates"
                    )

                seen_formats.add(export_format)

        if not isinstance(self.output_directory, str):
            errors.append(
                "export_request.output_directory must be a string"
            )
        elif not self.output_directory.strip():
            errors.append(
                "export_request.output_directory must not be empty"
            )

        if not isinstance(self.overwrite, bool):
            errors.append("export_request.overwrite must be a boolean")

        if not isinstance(self.metadata, dict):
            errors.append("export_request.metadata must be a dictionary")

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize this export request."""

        return {
            "source_path": self.source_path,
            "source_type": self.source_type.value,
            "formats": [
                export_format.value
                for export_format in self.formats
            ],
            "output_directory": self.output_directory,
            "overwrite": self.overwrite,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "ExportRequest":
        """Deserialize an export request."""

        return cls(
            source_path=data["source_path"],
            source_type=SourceReportType(data["source_type"]),
            formats=tuple(
                ExportFormat(value)
                for value in data.get("formats", [])
            ),
            output_directory=data["output_directory"],
            overwrite=data.get("overwrite", False),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    """One generated export artifact."""

    format: ExportFormat
    path: str
    size_bytes: int
    content_type: str
    checksum: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Return validation errors for this export artifact."""

        errors: list[str] = []

        if not isinstance(self.format, ExportFormat):
            errors.append(
                "export_artifact.format must be an ExportFormat"
            )

        if not isinstance(self.path, str):
            errors.append("export_artifact.path must be a string")
        elif not self.path.strip():
            errors.append("export_artifact.path must not be empty")

        if isinstance(self.size_bytes, bool) or not isinstance(
            self.size_bytes,
            int,
        ):
            errors.append(
                "export_artifact.size_bytes must be an integer"
            )
        elif self.size_bytes < 0:
            errors.append(
                "export_artifact.size_bytes must not be negative"
            )

        if not isinstance(self.content_type, str):
            errors.append(
                "export_artifact.content_type must be a string"
            )
        elif not self.content_type.strip():
            errors.append(
                "export_artifact.content_type must not be empty"
            )

        if self.checksum is not None:
            if not isinstance(self.checksum, str):
                errors.append(
                    "export_artifact.checksum must be a string or null"
                )
            elif not self.checksum.strip():
                errors.append(
                    "export_artifact.checksum must not be empty"
                )

        if not isinstance(self.metadata, dict):
            errors.append(
                "export_artifact.metadata must be a dictionary"
            )

        return errors

    @property
    def filename(self) -> str:
        """Return the artifact filename."""

        return Path(self.path).name

    def to_dict(self) -> dict[str, Any]:
        """Serialize this export artifact."""

        return {
            "format": self.format.value,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
            "checksum": self.checksum,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "ExportArtifact":
        """Deserialize an export artifact."""

        return cls(
            format=ExportFormat(data["format"]),
            path=data["path"],
            size_bytes=data["size_bytes"],
            content_type=data["content_type"],
            checksum=data.get("checksum"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class ExportSummary:
    """Aggregate summary of one export execution."""

    requested_count: int
    generated_count: int
    failed_count: int
    total_size_bytes: int

    def validate(self) -> list[str]:
        """Return validation errors for this export summary."""

        errors: list[str] = []

        values = {
            "requested_count": self.requested_count,
            "generated_count": self.generated_count,
            "failed_count": self.failed_count,
            "total_size_bytes": self.total_size_bytes,
        }

        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(
                    f"export_summary.{name} must be an integer"
                )
            elif value < 0:
                errors.append(
                    f"export_summary.{name} must not be negative"
                )

        if all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in values.values()
        ):
            if (
                self.generated_count + self.failed_count
                != self.requested_count
            ):
                errors.append(
                    "export_summary.generated_count + failed_count "
                    "must equal requested_count"
                )

        return errors

    def to_dict(self) -> dict[str, int]:
        """Serialize this export summary."""

        return {
            "requested_count": self.requested_count,
            "generated_count": self.generated_count,
            "failed_count": self.failed_count,
            "total_size_bytes": self.total_size_bytes,
        }

    @classmethod
    def from_artifacts(
        cls,
        *,
        requested_count: int,
        artifacts: Sequence[ExportArtifact],
        failed_count: int = 0,
    ) -> "ExportSummary":
        """Build a summary from generated artifacts."""

        normalized_artifacts = tuple(artifacts)

        return cls(
            requested_count=requested_count,
            generated_count=len(normalized_artifacts),
            failed_count=failed_count,
            total_size_bytes=sum(
                artifact.size_bytes
                for artifact in normalized_artifacts
            ),
        )

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "ExportSummary":
        """Deserialize an export summary."""

        return cls(
            requested_count=data["requested_count"],
            generated_count=data["generated_count"],
            failed_count=data["failed_count"],
            total_size_bytes=data["total_size_bytes"],
        )


@dataclass(frozen=True, slots=True)
class ExportReport:
    """Complete export execution report."""

    report_version: str
    exporter_version: str
    run_id: str
    generated_at: str
    status: str
    request: ExportRequest
    summary: ExportSummary
    artifacts: tuple[ExportArtifact, ...]
    errors: tuple[str, ...] = ()
    source_metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Return validation errors for this export report."""

        errors: list[str] = []

        for name, value in {
            "report_version": self.report_version,
            "exporter_version": self.exporter_version,
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "status": self.status,
        }.items():
            if not isinstance(value, str):
                errors.append(f"{name} must be a string")
            elif not value.strip():
                errors.append(f"{name} must not be empty")

        if isinstance(self.generated_at, str) and self.generated_at.strip():
            try:
                datetime.fromisoformat(
                    self.generated_at.replace("Z", "+00:00")
                )
            except ValueError:
                errors.append(
                    "generated_at must be a valid ISO-8601 datetime"
                )

        if not isinstance(self.request, ExportRequest):
            errors.append("request must be an ExportRequest")
        else:
            errors.extend(self.request.validate())

        if not isinstance(self.summary, ExportSummary):
            errors.append("summary must be an ExportSummary")
        else:
            errors.extend(self.summary.validate())

        if not isinstance(self.artifacts, tuple):
            errors.append("artifacts must be a tuple")
        else:
            artifact_paths: set[str] = set()
            artifact_formats: set[ExportFormat] = set()

            for index, artifact in enumerate(self.artifacts):
                if not isinstance(artifact, ExportArtifact):
                    errors.append(
                        f"artifacts[{index}] must be an ExportArtifact"
                    )
                    continue

                for artifact_error in artifact.validate():
                    errors.append(
                        f"artifacts[{index}].{artifact_error}"
                    )

                if artifact.path in artifact_paths:
                    errors.append(
                        "artifacts must not contain duplicate paths"
                    )

                if artifact.format in artifact_formats:
                    errors.append(
                        "artifacts must not contain duplicate formats"
                    )

                artifact_paths.add(artifact.path)
                artifact_formats.add(artifact.format)

        if not isinstance(self.errors, tuple):
            errors.append("errors must be a tuple")
        else:
            for index, error in enumerate(self.errors):
                if not isinstance(error, str):
                    errors.append(
                        f"errors[{index}] must be a string"
                    )
                elif not error.strip():
                    errors.append(
                        f"errors[{index}] must not be empty"
                    )

        if (
            isinstance(self.summary, ExportSummary)
            and isinstance(self.artifacts, tuple)
        ):
            if self.summary.generated_count != len(self.artifacts):
                errors.append(
                    "summary.generated_count must match artifacts length"
                )

            if self.summary.failed_count != len(self.errors):
                errors.append(
                    "summary.failed_count must match errors length"
                )

            expected_size = sum(
                artifact.size_bytes
                for artifact in self.artifacts
                if isinstance(artifact, ExportArtifact)
            )

            if self.summary.total_size_bytes != expected_size:
                errors.append(
                    "summary.total_size_bytes must match artifact sizes"
                )

        if not isinstance(self.source_metadata, dict):
            errors.append(
                "source_metadata must be a dictionary"
            )

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize this export report."""

        return {
            "report_version": self.report_version,
            "exporter_version": self.exporter_version,
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "status": self.status,
            "request": self.request.to_dict(),
            "summary": self.summary.to_dict(),
            "artifacts": [
                artifact.to_dict()
                for artifact in self.artifacts
            ],
            "errors": list(self.errors),
            "source_metadata": dict(self.source_metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "ExportReport":
        """Deserialize a complete export report."""

        return cls(
            report_version=data["report_version"],
            exporter_version=data["exporter_version"],
            run_id=data["run_id"],
            generated_at=data["generated_at"],
            status=data["status"],
            request=ExportRequest.from_dict(data["request"]),
            summary=ExportSummary.from_dict(data["summary"]),
            artifacts=tuple(
                ExportArtifact.from_dict(item)
                for item in data.get("artifacts", [])
            ),
            errors=tuple(data.get("errors", [])),
            source_metadata=dict(
                data.get("source_metadata", {})
            ),
        )


__all__ = [
    "ExportArtifact",
    "ExportFormat",
    "ExportReport",
    "ExportRequest",
    "ExportSummary",
    "SourceReportType",
]
