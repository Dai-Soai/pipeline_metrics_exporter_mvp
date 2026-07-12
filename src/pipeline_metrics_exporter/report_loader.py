"""Load and normalize RADAR_SERVICE observability report artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from pipeline_metrics_exporter.contract import SourceReportType


COMMON_REQUIRED_FIELDS = (
    "report_version",
    "run_id",
    "generated_at",
    "status",
)

VERSION_FIELDS = {
    SourceReportType.METRICS: "collector_version",
    SourceReportType.HEALTH: "analyzer_version",
    SourceReportType.TREND: "analyzer_version",
}


class ObservabilityReportLoadError(Exception):
    """Base exception raised while loading observability reports."""


class ObservabilityReportFileNotFoundError(
    ObservabilityReportLoadError
):
    """Raised when an observability report cannot be found."""


class ObservabilityReportJSONError(
    ObservabilityReportLoadError
):
    """Raised when an observability report contains malformed JSON."""


class ObservabilityReportValidationError(
    ObservabilityReportLoadError
):
    """Raised when an observability report violates the loader contract."""

    def __init__(
        self,
        errors: Sequence[str],
    ) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


class UnsupportedObservabilityReportError(
    ObservabilityReportLoadError
):
    """Raised when the loader cannot identify a supported report type."""


class DuplicateObservabilityReportError(
    ObservabilityReportLoadError
):
    """Raised when multiple reports share the same source type and run ID."""


@dataclass(frozen=True, slots=True)
class LoadedObservabilityReport:
    """Normalized representation of one observability report."""

    source_type: SourceReportType
    report_version: str
    producer_version: str
    run_id: str
    generated_at: str
    status: str
    sections: dict[str, Any]
    source_path: str | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)
    raw_report: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Return validation errors for this loaded report."""

        errors: list[str] = []

        if not isinstance(self.source_type, SourceReportType):
            errors.append(
                "loaded_report.source_type must be a SourceReportType"
            )

        for name, value in {
            "report_version": self.report_version,
            "producer_version": self.producer_version,
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "status": self.status,
        }.items():
            if not isinstance(value, str):
                errors.append(
                    f"loaded_report.{name} must be a string"
                )
            elif not value.strip():
                errors.append(
                    f"loaded_report.{name} must not be empty"
                )

        if not isinstance(self.sections, dict):
            errors.append(
                "loaded_report.sections must be a dictionary"
            )
        elif not self.sections:
            errors.append(
                "loaded_report.sections must not be empty"
            )

        if self.source_path is not None:
            if not isinstance(self.source_path, str):
                errors.append(
                    "loaded_report.source_path "
                    "must be a string or null"
                )
            elif not self.source_path.strip():
                errors.append(
                    "loaded_report.source_path must not be empty"
                )

        if not isinstance(self.source_metadata, dict):
            errors.append(
                "loaded_report.source_metadata "
                "must be a dictionary"
            )

        if not isinstance(self.raw_report, dict):
            errors.append(
                "loaded_report.raw_report must be a dictionary"
            )

        return errors

    @property
    def version_metadata(self) -> dict[str, str]:
        """Return normalized source version metadata."""

        return {
            "report_version": self.report_version,
            "producer_version": self.producer_version,
        }

    @property
    def identity(self) -> tuple[SourceReportType, str]:
        """Return the unique report identity used by collection loading."""

        return (
            self.source_type,
            self.run_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this normalized report."""

        return {
            "source_type": self.source_type.value,
            "report_version": self.report_version,
            "producer_version": self.producer_version,
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "status": self.status,
            "sections": dict(self.sections),
            "source_path": self.source_path,
            "source_metadata": dict(self.source_metadata),
            "raw_report": dict(self.raw_report),
        }


class ObservabilityReportLoader:
    """Load supported RADAR_SERVICE observability report artifacts."""

    def detect_source_type(
        self,
        data: Mapping[str, Any],
    ) -> SourceReportType:
        """Detect the observability report type from its structure."""

        if not isinstance(data, Mapping):
            raise ObservabilityReportValidationError(
                ["observability report root must be a JSON object"]
            )

        keys = set(data)

        metrics_signals = {
            "metrics",
            "runtime_metrics",
            "consumer_metrics",
            "latency_metrics",
        }

        health_signals = {
            "score",
            "findings",
            "overview",
        }

        trend_signals = {
            "samples",
            "metric_trends",
        }

        if trend_signals.issubset(keys):
            return SourceReportType.TREND

        if (
            "summary" in keys
            and "score" in keys
            and (
                "findings" in keys
                or "overview" in keys
            )
        ):
            return SourceReportType.HEALTH

        if (
            "collector_version" in keys
            or bool(metrics_signals.intersection(keys))
        ):
            return SourceReportType.METRICS

        raise UnsupportedObservabilityReportError(
            "Unable to detect supported observability report type"
        )

    def load(
        self,
        path: str | Path,
        *,
        expected_type: SourceReportType | None = None,
    ) -> LoadedObservabilityReport:
        """Load one observability JSON report."""

        report_path = Path(path).expanduser()

        if not report_path.exists():
            raise ObservabilityReportFileNotFoundError(
                f"Observability report not found: {report_path}"
            )

        if not report_path.is_file():
            raise ObservabilityReportLoadError(
                "Observability report path is not a file: "
                f"{report_path}"
            )

        try:
            data = json.loads(
                report_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise ObservabilityReportJSONError(
                f"Invalid JSON in observability report "
                f"{report_path}: {exc.msg} at line "
                f"{exc.lineno}, column {exc.colno}"
            ) from exc
        except OSError as exc:
            raise ObservabilityReportLoadError(
                f"Unable to read observability report "
                f"{report_path}: {exc}"
            ) from exc

        return self.from_dict(
            data,
            source_path=str(report_path.resolve()),
            expected_type=expected_type,
        )

    def from_dict(
        self,
        data: Mapping[str, Any],
        *,
        source_path: str | None = None,
        expected_type: SourceReportType | None = None,
    ) -> LoadedObservabilityReport:
        """Normalize one observability report dictionary."""

        if not isinstance(data, Mapping):
            raise ObservabilityReportValidationError(
                ["observability report root must be a JSON object"]
            )

        raw_report = dict(data)
        errors: list[str] = []

        if expected_type is not None and not isinstance(
            expected_type,
            SourceReportType,
        ):
            raise TypeError(
                "expected_type must be a SourceReportType or null"
            )

        source_type = self.detect_source_type(raw_report)

        if (
            expected_type is not None
            and source_type is not expected_type
        ):
            raise ObservabilityReportValidationError(
                [
                    "detected source type "
                    f"'{source_type.value}' does not match expected "
                    f"type '{expected_type.value}'"
                ]
            )

        producer_version_field = VERSION_FIELDS[source_type]

        required_fields = (
            *COMMON_REQUIRED_FIELDS,
            producer_version_field,
        )

        for field_name in required_fields:
            if field_name not in raw_report:
                errors.append(
                    f"missing required field: {field_name}"
                )
                continue

            value = raw_report[field_name]

            if not isinstance(value, str):
                errors.append(
                    f"{field_name} must be a string"
                )
            elif not value.strip():
                errors.append(
                    f"{field_name} must not be empty"
                )

        if source_path is not None:
            if not isinstance(source_path, str):
                errors.append(
                    "source_path must be a string or null"
                )
            elif not source_path.strip():
                errors.append(
                    "source_path must not be empty"
                )

        sections = self._extract_sections(
            raw_report,
            source_type,
        )

        if not sections:
            errors.append(
                f"{source_type.value} report contains no "
                "exportable sections"
            )

        source_metadata = raw_report.get(
            "source_metadata",
            {},
        )

        if not isinstance(source_metadata, Mapping):
            errors.append(
                "source_metadata must be a JSON object"
            )

        if errors:
            raise ObservabilityReportValidationError(errors)

        report = LoadedObservabilityReport(
            source_type=source_type,
            report_version=raw_report["report_version"],
            producer_version=raw_report[
                producer_version_field
            ],
            run_id=raw_report["run_id"],
            generated_at=raw_report["generated_at"],
            status=raw_report["status"],
            sections=sections,
            source_path=source_path,
            source_metadata=dict(source_metadata),
            raw_report=raw_report,
        )

        validation_errors = report.validate()

        if validation_errors:
            raise ObservabilityReportValidationError(
                validation_errors
            )

        return report

    def load_many(
        self,
        paths: Sequence[str | Path],
        *,
        expected_type: SourceReportType | None = None,
    ) -> tuple[LoadedObservabilityReport, ...]:
        """Load multiple reports and verify collection uniqueness."""

        reports = tuple(
            self.load(
                path,
                expected_type=expected_type,
            )
            for path in paths
        )

        return self._normalize_collection(reports)

    def load_directory(
        self,
        directory: str | Path,
        *,
        pattern: str = "*.json",
        recursive: bool = False,
        expected_type: SourceReportType | None = None,
    ) -> tuple[LoadedObservabilityReport, ...]:
        """Load supported reports from one directory."""

        directory_path = Path(directory).expanduser()

        if not directory_path.exists():
            raise ObservabilityReportFileNotFoundError(
                "Observability report directory not found: "
                f"{directory_path}"
            )

        if not directory_path.is_dir():
            raise ObservabilityReportLoadError(
                "Observability report path is not a directory: "
                f"{directory_path}"
            )

        candidates = (
            directory_path.rglob(pattern)
            if recursive
            else directory_path.glob(pattern)
        )

        paths = tuple(
            sorted(
                path
                for path in candidates
                if path.is_file()
            )
        )

        if not paths:
            raise ObservabilityReportFileNotFoundError(
                f"No observability reports matched '{pattern}' "
                f"in {directory_path}"
            )

        return self.load_many(
            paths,
            expected_type=expected_type,
        )

    def _extract_sections(
        self,
        report: Mapping[str, Any],
        source_type: SourceReportType,
    ) -> dict[str, Any]:
        """Extract exportable report sections."""

        if source_type is SourceReportType.METRICS:
            preferred_names = (
                "summary",
                "metrics",
                "runtime_metrics",
                "consumer_metrics",
                "latency_metrics",
                "sources",
            )
        elif source_type is SourceReportType.HEALTH:
            preferred_names = (
                "summary",
                "score",
                "overview",
                "findings",
            )
        else:
            preferred_names = (
                "summary",
                "overview",
                "samples",
                "metric_trends",
            )

        sections: dict[str, Any] = {}

        for name in preferred_names:
            if name in report:
                sections[name] = report[name]

        return sections

    def _normalize_collection(
        self,
        reports: tuple[LoadedObservabilityReport, ...],
    ) -> tuple[LoadedObservabilityReport, ...]:
        """Validate uniqueness and return deterministic ordering."""

        seen_identities: set[
            tuple[SourceReportType, str]
        ] = set()

        for index, report in enumerate(reports):
            if not isinstance(
                report,
                LoadedObservabilityReport,
            ):
                raise TypeError(
                    f"reports[{index}] must be a "
                    "LoadedObservabilityReport"
                )

            if report.identity in seen_identities:
                raise DuplicateObservabilityReportError(
                    "Duplicate observability report identity: "
                    f"{report.source_type.value}/"
                    f"{report.run_id}"
                )

            seen_identities.add(report.identity)

        return tuple(
            sorted(
                reports,
                key=lambda report: (
                    report.generated_at,
                    report.source_type.value,
                    report.run_id,
                ),
            )
        )


__all__ = [
    "COMMON_REQUIRED_FIELDS",
    "DuplicateObservabilityReportError",
    "LoadedObservabilityReport",
    "ObservabilityReportFileNotFoundError",
    "ObservabilityReportJSONError",
    "ObservabilityReportLoadError",
    "ObservabilityReportLoader",
    "ObservabilityReportValidationError",
    "UnsupportedObservabilityReportError",
    "VERSION_FIELDS",
]
