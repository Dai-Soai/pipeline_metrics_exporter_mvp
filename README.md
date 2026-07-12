# Pipeline Metrics Exporter MVP

Pipeline Metrics Exporter is Utility #29 of the RADAR_SERVICE
Runtime Observability Phase.

It converts observability report artifacts into portable formats for
analysis, sharing, dashboards, audits, and operational documentation.

## Purpose

Previous utilities generate structured JSON artifacts:

- Utility #26 — Pipeline Metrics Collector
- Utility #27 — Pipeline Health Analyzer
- Utility #28 — Pipeline Health Trend Analyzer

Utility #29 answers:

> How can these observability artifacts be exported into formats that
> people, spreadsheets, dashboards, and external tools can consume?

## Planned input artifacts

- Metrics reports
- Health reports
- Trend reports

## Planned export formats

- CSV
- Markdown
- HTML
- Excel

Excel support remains part of the Utility #29 roadmap and is not yet
implemented at M1.

## Planned capabilities

- Detect supported observability report types
- Load JSON report artifacts
- Normalize report metadata and tabular sections
- Export metrics into CSV
- Export summaries into Markdown
- Export reports into standalone HTML
- Export workbook artifacts
- Validate generated exports
- Inspect export manifests
- Provide an automation-friendly CLI
- Generate a JSON export report

## Planned architecture

```text
Observability JSON Artifact
            │
            ▼
ArtifactLoader
            │
            ▼
NormalizedExportModel
            │
            ▼
ExportEngine
            │
            ├── CSVExporter
            ├── MarkdownExporter
            ├── HTMLExporter
            └── ExcelExporter
            │
            ▼
Export Manifest / JSON Report
```

## Roadmap

- M1 — Bootstrap Project
- M2 — Export Contract
- M3 — Observability Report Loader
- M4 — CSV Exporter
- M5 — Markdown and HTML Exporters
- M6 — Excel Exporter
- M7 — Export Engine
- M8 — CLI and JSON Export Report
- M9 — Packaging & README
- M10 — Release v0.1.0

Small enhancements may be inserted as `M8.1`, `M8.2`, and later
sub-milestones when needed without restructuring the complete roadmap.

## Project status

Current status: **RELEASED v0.1.0**

Version: `0.1.0`

Status: `ACTIVE / UNLOCKED`

## Export contract

The core contract includes:

- `ExportFormat`
- `SourceReportType`
- `ExportRequest`
- `ExportArtifact`
- `ExportSummary`
- `ExportReport`

The contract supports:

- Validation
- Serialization
- Deserialization
- Exporter and report version metadata
- Multiple requested export formats
- Generated artifact metadata
- Artifact checksum metadata
- Export size aggregation
- Failure tracking
- Duplicate path and format detection
- Summary consistency validation

## Observability report loader

The loader supports JSON artifacts produced by:

- Utility #26 — Pipeline Metrics Collector
- Utility #27 — Pipeline Health Analyzer
- Utility #28 — Pipeline Health Trend Analyzer

Capabilities:

- Automatic source report type detection
- Explicit expected-type enforcement
- Metrics, health, and trend report loading
- Single-file loading
- Multiple-file loading
- Directory loading
- Recursive discovery
- JSON syntax validation
- Required metadata validation
- Producer version normalization
- Exportable section extraction
- Source path and metadata preservation
- Duplicate source identity detection

Every supported input is normalized into a
`LoadedObservabilityReport`.

## CSV exporter

The CSV exporter converts metrics, health, and trend reports into a
consistent long-form table.

Columns:

- `source_type`
- `run_id`
- `generated_at`
- `status`
- `section`
- `path`
- `value`
- `value_type`

Nested mappings and arrays are flattened into paths such as:

- `execution_failed`
- `findings[0].severity`
- `samples[0].health_score`
- `metric_trends[0].direction`

Generated CSV artifacts include:

- Absolute artifact path
- UTF-8 byte size
- `text/csv` content type
- SHA-256 checksum
- Source report metadata
- Exported row count
- Exported section count

The exporter performs atomic writes and rejects accidental overwrites
unless `overwrite=True` is explicitly enabled.

## Markdown exporter

The Markdown exporter produces GitHub-compatible operational reports.

Features:

- Report metadata table
- One table per exportable section
- Nested mapping and array path preservation
- Source metadata table
- Markdown table escaping
- Atomic writes
- SHA-256 checksums
- Explicit overwrite protection

## HTML exporter

The HTML exporter produces a standalone browser report.

Features:

- Embedded responsive CSS
- Report metadata cards
- One table per exportable section
- Source metadata table
- HTML escaping for source values
- No external runtime assets
- Atomic writes
- SHA-256 checksums
- Explicit overwrite protection

## Excel exporter

The Excel exporter produces a formatted `.xlsx` workbook using the
Office Open XML spreadsheet standard.

Workbook layout:

- `Metadata`
- One worksheet for each exportable report section
- `Source Metadata` when source metadata is available

Each data worksheet includes:

- Document title
- Frozen title and header rows
- Auto-filter
- Formatted column headers
- Wrapped text cells
- Numeric and boolean cell types
- Controlled column widths
- Preserved nested array paths

Generated Excel artifacts include:

- Absolute workbook path
- Workbook byte size
- Excel content type
- SHA-256 checksum
- Sheet count
- Sheet names
- Source report metadata

The exporter performs atomic writes and rejects accidental overwrites
unless `overwrite=True` is explicitly supplied.

## Export engine

`ExportEngine` provides one unified API for all supported exporters.

Execution flow:

```text
ExportRequest
      │
      ▼
ObservabilityReportLoader
      │
      ▼
LoadedObservabilityReport
      │
      ▼
ExportEngine
      ├── CSVExporter
      ├── MarkdownExporter
      ├── HTMLExporter
      └── ExcelExporter
      │
      ▼
ExportReport
```

The engine supports:

- Multi-format export requests
- Source report type enforcement
- Already-loaded report execution
- Configurable exporter registries
- Per-format error isolation
- Completed, partial, and failed statuses
- Artifact type and format validation
- Aggregate artifact size calculation
- Source metadata propagation
- Unique export run identifiers
- UTC generation timestamps
- Exporter version metadata

A failure in one exporter does not discard successful artifacts produced
by other formats.

### Version metadata isolation

Package version metadata is defined in:

```text
pipeline_metrics_exporter._version
```

Both the package public API and the export engine consume this isolated
module. This prevents circular imports while preserving consistent
`exporter_version` metadata across generated export reports.

## Command-line interface

Installed command:

```bash
pipeline-metrics-exporter
```

### Export

```bash
pipeline-metrics-exporter export   examples/input/metrics_report.json   --type metrics   --formats csv,markdown,html,excel   --output reports   --report-output reports/export_report.json   --overwrite
```

### Validate

```bash
pipeline-metrics-exporter validate   reports/export_report.json   --verify-artifacts   --verify-checksums
```

### Inspect

```bash
pipeline-metrics-exporter inspect   reports/export_report.json
```

Machine-readable inspection:

```bash
pipeline-metrics-exporter inspect   reports/export_report.json   --json
```

### Version

```bash
pipeline-metrics-exporter version
```

## JSON export report

Every CLI export can generate a structured `export_report.json`
containing:

- `report_version`
- `exporter_version`
- `run_id`
- `generated_at`
- `status`
- original export request
- export summary
- generated artifacts
- per-format errors
- normalized source metadata

JSON report operations support atomic writes, overwrite protection,
contract validation, artifact existence checks, byte-size checks, and
SHA-256 checksum verification.

## Architecture

```text
Metrics / Health / Trend JSON Report
                 │
                 ▼
    ObservabilityReportLoader
                 │
                 ▼
    LoadedObservabilityReport
                 │
                 ▼
             ExportEngine
        ┌────────┼─────────┬─────────┐
        ▼        ▼         ▼         ▼
       CSV    Markdown    HTML      Excel
        │        │         │         │
        └────────┴─────────┴─────────┘
                 │
                 ▼
            ExportReport
                 │
                 ▼
        export_report.json
```

## Supported source reports

The exporter accepts normalized observability reports produced by:

- Pipeline Metrics Collector
- Pipeline Health Analyzer
- Pipeline Health Trend Analyzer

Supported source types:

- `metrics`
- `health`
- `trend`

## Supported output formats

| Format | Extension | Primary use |
|---|---:|---|
| CSV | `.csv` | Data processing and analysis |
| Markdown | `.md` | GitHub and operational documentation |
| HTML | `.html` | Standalone browser reports |
| Excel | `.xlsx` | Spreadsheet analysis and sharing |

## Installation

Install from a wheel:

```bash
python -m pip install   dist/pipeline_metrics_exporter-0.1.0-py3-none-any.whl
```

Editable development installation:

```bash
python -m pip install -e ".[dev]"
```

## CLI quick start

Export all supported formats:

```bash
pipeline-metrics-exporter export   examples/input/metrics_report.json   --type metrics   --formats csv,markdown,html,excel   --output reports   --report-output reports/export_report.json   --overwrite
```

Validate the generated export report and artifact integrity:

```bash
pipeline-metrics-exporter validate   reports/export_report.json   --verify-artifacts   --verify-checksums
```

Inspect the export report:

```bash
pipeline-metrics-exporter inspect   reports/export_report.json
```

Display the installed version:

```bash
pipeline-metrics-exporter version
```

## Python API

```python
from pipeline_metrics_exporter import (
    ExportEngine,
    ExportFormat,
    ExportRequest,
    SourceReportType,
)

request = ExportRequest(
    source_path="metrics_report.json",
    source_type=SourceReportType.METRICS,
    formats=(
        ExportFormat.CSV,
        ExportFormat.MARKDOWN,
        ExportFormat.HTML,
        ExportFormat.EXCEL,
    ),
    output_directory="reports",
    overwrite=True,
)

report = ExportEngine().execute(request)

print(report.status)
print(report.summary.generated_count)
```

## Export report metadata

Each structured export report includes:

- `report_version`
- `exporter_version`
- `run_id`
- `generated_at`
- `status`
- original export request
- export summary
- generated artifact records
- per-format errors
- normalized source metadata

Each generated artifact includes:

- output format
- absolute file path
- byte size
- content type
- SHA-256 checksum
- format-specific metadata

## Integrity and safety

The utility provides:

- Source report contract validation
- Requested source-type enforcement
- Atomic artifact writes
- Explicit overwrite protection
- Per-format failure isolation
- Artifact type validation
- Artifact format validation
- Artifact existence verification
- Artifact byte-size verification
- SHA-256 checksum verification
- Completed, partial, and failed statuses

## Package typing

The distribution includes:

```text
pipeline_metrics_exporter/py.typed
```

This marker declares the installed package as a typed package under
PEP 561. Static type checkers can therefore consume the annotations
provided directly by the package.

## Project structure

```text
pipeline_metrics_exporter_mvp/
├── examples/
│   ├── input/
│   └── output/
├── reports/
├── src/
│   └── pipeline_metrics_exporter/
│       ├── __init__.py
│       ├── _version.py
│       ├── cli.py
│       ├── contract.py
│       ├── csv_exporter.py
│       ├── excel_exporter.py
│       ├── export_engine.py
│       ├── html_exporter.py
│       ├── markdown_exporter.py
│       ├── presentation.py
│       ├── py.typed
│       ├── report_io.py
│       └── report_loader.py
├── tests/
├── CHANGELOG.md
├── LICENSE
├── README.md
├── RELEASE_NOTES.md
├── pyproject.toml
└── pytest.ini
```

Generated reports, build products, virtual environments, and cache
directories are excluded from version control and release source code.

## Release validation

Version `0.1.0` is verified through:

- 101 automated tests
- Wheel build
- Source distribution build
- Wheel metadata inspection
- Wheel content inspection
- `py.typed` package-data verification
- Clean wheel installation
- Installed package import verification
- Installed CLI verification
- Four-format export verification
- JSON report validation
- Artifact existence verification
- Artifact byte-size verification
- SHA-256 checksum verification

## Distribution artifacts

```text
pipeline_metrics_exporter-0.1.0-py3-none-any.whl
pipeline_metrics_exporter-0.1.0.tar.gz
```

## Status

Utility #29 — Pipeline Metrics Exporter MVP is released as version
`0.1.0`.

Formal snapshot artifacts and the Utility #29 lock are maintained in
the dedicated `radar_service_snapshots` repository.
