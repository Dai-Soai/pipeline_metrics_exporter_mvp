# Pipeline Metrics Exporter MVP v0.1.0

## Overview

Pipeline Metrics Exporter MVP is Utility #29 of the RADAR_SERVICE
Runtime Observability Phase.

The utility consumes normalized metrics, health, and trend JSON
reports and exports them into formats suitable for analysis,
documentation, browser viewing, and spreadsheet workflows.

## Main capabilities

- Load normalized metrics reports.
- Load normalized pipeline health reports.
- Load normalized pipeline health trend reports.
- Validate source report type and metadata.
- Export flattened long-form CSV artifacts.
- Export GitHub-compatible Markdown reports.
- Export standalone HTML reports.
- Export formatted Office Open XML workbooks.
- Preserve nested mapping and array paths.
- Execute multiple requested formats through one export engine.
- Isolate failures between individual exporters.
- Generate completed, partial, and failed execution statuses.
- Generate structured JSON export reports.
- Validate and inspect JSON export reports.
- Verify generated artifact existence and byte size.
- Verify SHA-256 artifact checksums.
- Operate through an installed command-line interface.

## Supported formats

- CSV (`.csv`)
- Markdown (`.md`)
- HTML (`.html`)
- Excel (`.xlsx`)

## Installed command

```bash
pipeline-metrics-exporter
```

## Main commands

```bash
pipeline-metrics-exporter export ...
pipeline-metrics-exporter validate ...
pipeline-metrics-exporter inspect ...
pipeline-metrics-exporter version
```

## Version metadata

Generated export reports include:

- `report_version`
- `exporter_version`
- `run_id`
- `generated_at`
- `status`

## Release validation

- Automated tests: 101 passed
- CSV export: verified
- Markdown export: verified
- HTML export: verified
- Excel export: verified
- Unified export engine: verified
- Installed CLI: verified
- JSON export report: verified
- Artifact size validation: verified
- SHA-256 checksum validation: verified
- Wheel build: verified
- Source distribution build: verified
- Clean wheel installation: verified
- `py.typed` package marker: verified

## Distribution artifacts

- `pipeline_metrics_exporter-0.1.0-py3-none-any.whl`
- `pipeline_metrics_exporter-0.1.0.tar.gz`

## Status

Utility #29 is released as version `0.1.0`.

Snapshot Markdown, Snapshot YAML, and the formal Utility #29 lock are
maintained in the dedicated RADAR_SERVICE snapshot repository after
GitHub Release verification.
