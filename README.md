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

Current milestone: **M2 — Export Contract**

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
