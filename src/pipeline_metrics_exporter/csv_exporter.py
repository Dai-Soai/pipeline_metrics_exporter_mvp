"""CSV exporter for normalized RADAR_SERVICE observability reports."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline_metrics_exporter.contract import (
    ExportArtifact,
    ExportFormat,
)
from pipeline_metrics_exporter.report_loader import (
    LoadedObservabilityReport,
)


CSV_CONTENT_TYPE = "text/csv"
CSV_COLUMNS = (
    "source_type",
    "run_id",
    "generated_at",
    "status",
    "section",
    "path",
    "value",
    "value_type",
)


class CSVExportError(Exception):
    """Base exception raised while exporting CSV artifacts."""


class CSVExportFileExistsError(CSVExportError):
    """Raised when an output file exists and overwrite is disabled."""


@dataclass(frozen=True, slots=True)
class CSVRow:
    """One normalized long-form CSV row."""

    source_type: str
    run_id: str
    generated_at: str
    status: str
    section: str
    path: str
    value: str
    value_type: str

    def to_dict(self) -> dict[str, str]:
        """Serialize this row for csv.DictWriter."""

        return {
            "source_type": self.source_type,
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "status": self.status,
            "section": self.section,
            "path": self.path,
            "value": self.value,
            "value_type": self.value_type,
        }


class CSVExporter:
    """Export a normalized observability report to long-form CSV."""

    def build_rows(
        self,
        report: LoadedObservabilityReport,
    ) -> tuple[CSVRow, ...]:
        """Convert all report sections into normalized CSV rows."""

        self._validate_report(report)

        rows: list[CSVRow] = []

        for section_name, section_value in report.sections.items():
            initial_path = (
                section_name
                if isinstance(section_value, Sequence)
                and not isinstance(
                    section_value,
                    (str, bytes, bytearray),
                )
                else ""
            )

            flattened_values = self._flatten(
                section_value,
                path=initial_path,
            )

            for path, value, value_type in flattened_values:
                rows.append(
                    CSVRow(
                        source_type=report.source_type.value,
                        run_id=report.run_id,
                        generated_at=report.generated_at,
                        status=report.status,
                        section=section_name,
                        path=path or section_name,
                        value=value,
                        value_type=value_type,
                    )
                )

        return tuple(rows)

    def render(
        self,
        report: LoadedObservabilityReport,
    ) -> str:
        """Render one normalized report as CSV text."""

        rows = self.build_rows(report)

        from io import StringIO

        buffer = StringIO(newline="")

        writer = csv.DictWriter(
            buffer,
            fieldnames=CSV_COLUMNS,
            lineterminator="\n",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row.to_dict())

        return buffer.getvalue()

    def export(
        self,
        report: LoadedObservabilityReport,
        output_directory: str | Path,
        *,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> ExportArtifact:
        """Write a CSV artifact and return its artifact contract."""

        self._validate_report(report)

        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean")

        output_path = Path(output_directory).expanduser()

        if filename is None:
            filename = (
                f"{report.source_type.value}_"
                f"{self._safe_filename(report.run_id)}.csv"
            )
        else:
            if not isinstance(filename, str):
                raise TypeError("filename must be a string")

            if not filename.strip():
                raise ValueError("filename must not be empty")

            filename = self._safe_filename(filename)

            if not filename.lower().endswith(".csv"):
                filename += ".csv"

        output_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        artifact_path = output_path / filename

        if artifact_path.exists() and not overwrite:
            raise CSVExportFileExistsError(
                f"CSV artifact already exists: {artifact_path}"
            )

        content = self.render(report)
        encoded_content = content.encode("utf-8")

        temporary_path = artifact_path.with_name(
            f".{artifact_path.name}.tmp"
        )

        try:
            temporary_path.write_bytes(encoded_content)

            os.replace(
                temporary_path,
                artifact_path,
            )
        except OSError as exc:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

            raise CSVExportError(
                f"Unable to write CSV artifact "
                f"{artifact_path}: {exc}"
            ) from exc

        rows = self.build_rows(report)
        checksum = hashlib.sha256(encoded_content).hexdigest()

        artifact = ExportArtifact(
            format=ExportFormat.CSV,
            path=str(artifact_path.resolve()),
            size_bytes=len(encoded_content),
            content_type=CSV_CONTENT_TYPE,
            checksum=f"sha256:{checksum}",
            metadata={
                "source_type": report.source_type.value,
                "source_run_id": report.run_id,
                "row_count": len(rows),
                "section_count": len(report.sections),
                "columns": list(CSV_COLUMNS),
                "encoding": "utf-8",
                "layout": "long-form",
            },
        )

        errors = artifact.validate()

        if errors:
            raise CSVExportError("; ".join(errors))

        return artifact

    def _flatten(
        self,
        value: Any,
        *,
        path: str,
    ) -> tuple[tuple[str, str, str], ...]:
        """Flatten nested mappings and sequences into scalar rows."""

        rows: list[tuple[str, str, str]] = []

        if isinstance(value, Mapping):
            if not value:
                rows.append(
                    (
                        path,
                        "{}",
                        "object",
                    )
                )
            else:
                for key, nested_value in value.items():
                    nested_path = (
                        f"{path}.{key}"
                        if path
                        else str(key)
                    )

                    rows.extend(
                        self._flatten(
                            nested_value,
                            path=nested_path,
                        )
                    )

            return tuple(rows)

        if (
            isinstance(value, Sequence)
            and not isinstance(
                value,
                (str, bytes, bytearray),
            )
        ):
            if not value:
                rows.append(
                    (
                        path,
                        "[]",
                        "array",
                    )
                )
            else:
                for index, nested_value in enumerate(value):
                    nested_path = f"{path}[{index}]"

                    rows.extend(
                        self._flatten(
                            nested_value,
                            path=nested_path,
                        )
                    )

            return tuple(rows)

        return (
            (
                path,
                self._format_value(value),
                self._value_type(value),
            ),
        )

    def _format_value(self, value: Any) -> str:
        """Format a scalar value consistently."""

        if value is None:
            return ""

        if isinstance(value, bool):
            return "true" if value else "false"

        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, str):
            return value

        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
        )

    def _value_type(self, value: Any) -> str:
        """Return the normalized scalar type name."""

        if value is None:
            return "null"

        if isinstance(value, bool):
            return "boolean"

        if isinstance(value, int):
            return "integer"

        if isinstance(value, float):
            return "number"

        if isinstance(value, str):
            return "string"

        return type(value).__name__

    def _safe_filename(self, value: str) -> str:
        """Return a filesystem-safe filename component."""

        normalized = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            value.strip(),
        )

        normalized = normalized.strip("._")

        if not normalized:
            raise ValueError(
                "filename does not contain any safe characters"
            )

        return normalized

    def _validate_report(
        self,
        report: LoadedObservabilityReport,
    ) -> None:
        """Validate a normalized source report."""

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


__all__ = [
    "CSV_COLUMNS",
    "CSV_CONTENT_TYPE",
    "CSVExportError",
    "CSVExportFileExistsError",
    "CSVExporter",
    "CSVRow",
]
