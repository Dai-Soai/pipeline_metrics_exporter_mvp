"""Excel Open XML exporter for RADAR_SERVICE observability reports.

The exporter creates standards-compliant .xlsx workbooks using only
Python's standard library. Each report section is written to an
independent worksheet, together with metadata and source metadata.
"""

from __future__ import annotations

import hashlib
import os
import re
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from pipeline_metrics_exporter.contract import (
    ExportArtifact,
    ExportFormat,
)
from pipeline_metrics_exporter.presentation import (
    flatten_values,
    safe_filename,
)
from pipeline_metrics_exporter.report_loader import (
    LoadedObservabilityReport,
)


EXCEL_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)

EXCEL_COLUMNS = (
    "Path",
    "Value",
    "Type",
)

_INVALID_SHEET_CHARACTERS = re.compile(r"[\[\]:*?/\\]")


class ExcelExportError(Exception):
    """Base exception raised while exporting Excel workbooks."""


class ExcelExportFileExistsError(ExcelExportError):
    """Raised when an Excel artifact exists and overwrite is disabled."""


@dataclass(frozen=True, slots=True)
class ExcelSheet:
    """Normalized worksheet definition."""

    name: str
    title: str
    rows: tuple[tuple[Any, ...], ...]
    column_widths: tuple[float, ...]


class ExcelExporter:
    """Export observability reports as formatted .xlsx workbooks."""

    def build_sheets(
        self,
        report: LoadedObservabilityReport,
    ) -> tuple[ExcelSheet, ...]:
        """Build normalized worksheets for a loaded report."""

        self._validate_report(report)

        sheets: list[ExcelSheet] = []
        used_names: set[str] = set()

        metadata_rows = (
            ("Field", "Value"),
            ("Source type", report.source_type.value),
            ("Report version", report.report_version),
            ("Producer version", report.producer_version),
            ("Run ID", report.run_id),
            ("Generated at", report.generated_at),
            ("Status", report.status),
            (
                "Source path",
                report.source_path or "",
            ),
        )

        sheets.append(
            ExcelSheet(
                name=self._unique_sheet_name(
                    "Metadata",
                    used_names,
                ),
                title=(
                    f"{report.source_type.value.title()} "
                    "Observability Report"
                ),
                rows=metadata_rows,
                column_widths=(24.0, 70.0),
            )
        )

        for section_name, section_value in report.sections.items():
            initial_path = (
                section_name
                if self._is_sequence(section_value)
                else ""
            )

            flattened = flatten_values(
                section_value,
                path=initial_path,
            )

            rows: list[tuple[Any, ...]] = [
                EXCEL_COLUMNS,
            ]

            rows.extend(
                (
                    path or section_name,
                    self._typed_value(
                        value,
                        type_name,
                    ),
                    type_name,
                )
                for path, value, type_name in flattened
            )

            display_name = (
                section_name
                .replace("_", " ")
                .title()
            )

            sheets.append(
                ExcelSheet(
                    name=self._unique_sheet_name(
                        display_name,
                        used_names,
                    ),
                    title=display_name,
                    rows=tuple(rows),
                    column_widths=(46.0, 60.0, 16.0),
                )
            )

        if report.source_metadata:
            rows = [EXCEL_COLUMNS]

            rows.extend(
                (
                    path,
                    self._typed_value(
                        value,
                        type_name,
                    ),
                    type_name,
                )
                for path, value, type_name in flatten_values(
                    report.source_metadata
                )
            )

            sheets.append(
                ExcelSheet(
                    name=self._unique_sheet_name(
                        "Source Metadata",
                        used_names,
                    ),
                    title="Source Metadata",
                    rows=tuple(rows),
                    column_widths=(46.0, 60.0, 16.0),
                )
            )

        return tuple(sheets)

    def export(
        self,
        report: LoadedObservabilityReport,
        output_directory: str | Path,
        *,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> ExportArtifact:
        """Write a formatted .xlsx workbook."""

        self._validate_report(report)

        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean")

        directory = Path(output_directory).expanduser()
        directory.mkdir(parents=True, exist_ok=True)

        if filename is None:
            filename = (
                f"{report.source_type.value}_"
                f"{safe_filename(report.run_id)}.xlsx"
            )
        else:
            filename = safe_filename(filename)

            if not filename.lower().endswith(".xlsx"):
                filename += ".xlsx"

        artifact_path = directory / filename

        if artifact_path.exists() and not overwrite:
            raise ExcelExportFileExistsError(
                f"Excel artifact already exists: {artifact_path}"
            )

        sheets = self.build_sheets(report)

        temporary_path = artifact_path.with_name(
            f".{artifact_path.name}.tmp"
        )

        try:
            self._write_workbook(
                temporary_path,
                sheets,
            )

            os.replace(
                temporary_path,
                artifact_path,
            )
        except Exception as exc:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

            if isinstance(exc, ExcelExportError):
                raise

            raise ExcelExportError(
                "Unable to write Excel artifact "
                f"{artifact_path}: {exc}"
            ) from exc

        encoded = artifact_path.read_bytes()
        checksum = hashlib.sha256(encoded).hexdigest()

        artifact = ExportArtifact(
            format=ExportFormat.EXCEL,
            path=str(artifact_path.resolve()),
            size_bytes=len(encoded),
            content_type=EXCEL_CONTENT_TYPE,
            checksum=f"sha256:{checksum}",
            metadata={
                "source_type": report.source_type.value,
                "source_run_id": report.run_id,
                "sheet_count": len(sheets),
                "sheet_names": [
                    sheet.name
                    for sheet in sheets
                ],
                "encoding": "utf-8",
                "workbook_format": "xlsx",
                "spreadsheet_standard": "Office Open XML",
            },
        )

        errors = artifact.validate()

        if errors:
            raise ExcelExportError("; ".join(errors))

        return artifact

    def inspect_workbook(
        self,
        path: str | Path,
    ) -> dict[str, Any]:
        """Inspect the structure of a generated workbook."""

        workbook_path = Path(path).expanduser()

        if not workbook_path.exists():
            raise ExcelExportError(
                f"Excel artifact not found: {workbook_path}"
            )

        if not workbook_path.is_file():
            raise ExcelExportError(
                "Excel artifact path is not a file: "
                f"{workbook_path}"
            )

        try:
            with zipfile.ZipFile(workbook_path) as archive:
                names = set(archive.namelist())

                required = {
                    "[Content_Types].xml",
                    "_rels/.rels",
                    "xl/workbook.xml",
                    "xl/_rels/workbook.xml.rels",
                    "xl/styles.xml",
                    "docProps/core.xml",
                    "docProps/app.xml",
                }

                missing = sorted(required - names)

                worksheet_names = sorted(
                    name
                    for name in names
                    if (
                        name.startswith("xl/worksheets/sheet")
                        and name.endswith(".xml")
                    )
                )

                workbook_xml = archive.read(
                    "xl/workbook.xml"
                ).decode("utf-8")

                return {
                    "valid_zip": True,
                    "missing_required_entries": missing,
                    "worksheet_count": len(worksheet_names),
                    "worksheet_entries": worksheet_names,
                    "has_styles": "xl/styles.xml" in names,
                    "has_workbook": "xl/workbook.xml" in names,
                    "workbook_xml": workbook_xml,
                }
        except zipfile.BadZipFile as exc:
            raise ExcelExportError(
                f"Invalid Excel workbook archive: {workbook_path}"
            ) from exc

    def _write_workbook(
        self,
        path: Path,
        sheets: tuple[ExcelSheet, ...],
    ) -> None:
        """Write all Office Open XML workbook parts."""

        if not sheets:
            raise ExcelExportError(
                "Excel workbook must contain at least one sheet"
            )

        with zipfile.ZipFile(
            path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            archive.writestr(
                "[Content_Types].xml",
                self._content_types_xml(len(sheets)),
            )

            archive.writestr(
                "_rels/.rels",
                self._root_relationships_xml(),
            )

            archive.writestr(
                "docProps/core.xml",
                self._core_properties_xml(),
            )

            archive.writestr(
                "docProps/app.xml",
                self._app_properties_xml(sheets),
            )

            archive.writestr(
                "xl/workbook.xml",
                self._workbook_xml(sheets),
            )

            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                self._workbook_relationships_xml(
                    len(sheets)
                ),
            )

            archive.writestr(
                "xl/styles.xml",
                self._styles_xml(),
            )

            for index, sheet in enumerate(
                sheets,
                start=1,
            ):
                archive.writestr(
                    f"xl/worksheets/sheet{index}.xml",
                    self._worksheet_xml(sheet),
                )

    def _worksheet_xml(
        self,
        sheet: ExcelSheet,
    ) -> str:
        """Render a formatted worksheet XML document."""

        total_rows = len(sheet.rows)
        max_columns = max(
            (
                len(row)
                for row in sheet.rows
            ),
            default=1,
        )

        last_column = self._column_name(max_columns)

        column_xml = "".join(
            (
                f'<col min="{index}" max="{index}" '
                f'width="{width}" customWidth="1"/>'
            )
            for index, width in enumerate(
                sheet.column_widths,
                start=1,
            )
        )

        row_xml_parts: list[str] = []

        title_row = (
            '<row r="1" ht="26" customHeight="1">'
            f'<c r="A1" s="1" t="inlineStr">'
            f'<is><t>{escape(sheet.title)}</t></is>'
            "</c>"
            "</row>"
        )

        row_xml_parts.append(title_row)

        for row_index, row in enumerate(
            sheet.rows,
            start=3,
        ):
            style_index = 2 if row_index == 3 else 0

            cells = "".join(
                self._cell_xml(
                    row_index,
                    column_index,
                    value,
                    style_index=style_index,
                )
                for column_index, value in enumerate(
                    row,
                    start=1,
                )
            )

            row_xml_parts.append(
                f'<row r="{row_index}">{cells}</row>'
            )

        auto_filter = ""

        if total_rows > 1:
            auto_filter = (
                f'<autoFilter ref="A3:{last_column}'
                f'{total_rows + 2}"/>'
            )

        merged_title = (
            f'<mergeCells count="1">'
            f'<mergeCell ref="A1:{last_column}1"/>'
            "</mergeCells>"
        )

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main">'
            '<sheetViews>'
            '<sheetView workbookViewId="0">'
            '<pane ySplit="3" topLeftCell="A4" '
            'activePane="bottomLeft" state="frozen"/>'
            '<selection pane="bottomLeft" activeCell="A4" '
            'sqref="A4"/>'
            '</sheetView>'
            '</sheetViews>'
            '<sheetFormatPr defaultRowHeight="15"/>'
            f'<cols>{column_xml}</cols>'
            f'<sheetData>{"".join(row_xml_parts)}</sheetData>'
            f'{auto_filter}'
            f'{merged_title}'
            '<pageMargins left="0.7" right="0.7" '
            'top="0.75" bottom="0.75" '
            'header="0.3" footer="0.3"/>'
            '</worksheet>'
        )

    def _cell_xml(
        self,
        row_index: int,
        column_index: int,
        value: Any,
        *,
        style_index: int,
    ) -> str:
        """Render one worksheet cell."""

        reference = (
            f"{self._column_name(column_index)}"
            f"{row_index}"
        )

        if value is None:
            return (
                f'<c r="{reference}" s="{style_index}" '
                't="inlineStr"><is><t></t></is></c>'
            )

        if isinstance(value, bool):
            return (
                f'<c r="{reference}" s="{style_index}" t="b">'
                f"<v>{1 if value else 0}</v>"
                "</c>"
            )

        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            number_style = (
                3
                if isinstance(value, float)
                else style_index
            )

            return (
                f'<c r="{reference}" s="{number_style}">'
                f"<v>{value}</v>"
                "</c>"
            )

        text = str(value)
        preserve = (
            ' xml:space="preserve"'
            if (
                text.startswith(" ")
                or text.endswith(" ")
                or "\n" in text
            )
            else ""
        )

        return (
            f'<c r="{reference}" s="{style_index}" '
            't="inlineStr">'
            f"<is><t{preserve}>{escape(text)}</t></is>"
            "</c>"
        )

    def _typed_value(
        self,
        value: str,
        type_name: str,
    ) -> Any:
        """Recover native spreadsheet types from flattened values."""

        if type_name == "integer":
            try:
                return int(value)
            except ValueError:
                return value

        if type_name == "number":
            try:
                return float(value)
            except ValueError:
                return value

        if type_name == "boolean":
            return value.lower() == "true"

        if type_name == "null":
            return None

        return value

    def _unique_sheet_name(
        self,
        value: str,
        used_names: set[str],
    ) -> str:
        """Return a valid and unique Excel sheet name."""

        normalized = _INVALID_SHEET_CHARACTERS.sub(
            "_",
            value.strip(),
        )

        normalized = normalized.strip("'")

        if not normalized:
            normalized = "Sheet"

        normalized = normalized[:31]

        candidate = normalized
        suffix = 2

        while candidate.casefold() in used_names:
            suffix_text = f" {suffix}"
            candidate = (
                normalized[: 31 - len(suffix_text)]
                + suffix_text
            )
            suffix += 1

        used_names.add(candidate.casefold())
        return candidate

    def _column_name(self, index: int) -> str:
        """Convert a one-based column index to Excel letters."""

        if index < 1:
            raise ValueError(
                "column index must be greater than zero"
            )

        letters: list[str] = []

        while index:
            index, remainder = divmod(index - 1, 26)
            letters.append(chr(65 + remainder))

        return "".join(reversed(letters))

    def _is_sequence(self, value: Any) -> bool:
        return (
            isinstance(value, Sequence)
            and not isinstance(
                value,
                (str, bytes, bytearray),
            )
        )

    def _validate_report(
        self,
        report: LoadedObservabilityReport,
    ) -> None:
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

    def _content_types_xml(
        self,
        sheet_count: int,
    ) -> str:
        worksheets = "".join(
            (
                '<Override '
                f'PartName="/xl/worksheets/sheet{index}.xml" '
                'ContentType="application/vnd.openxmlformats-'
                'officedocument.spreadsheetml.worksheet+xml"/>'
            )
            for index in range(1, sheet_count + 1)
        )

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/'
            'package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.'
            'relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-'
            'officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-'
            'officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" '
            'ContentType="application/vnd.openxmlformats-package.'
            'core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" '
            'ContentType="application/vnd.openxmlformats-'
            'officedocument.extended-properties+xml"/>'
            f"{worksheets}"
            "</Types>"
        )

    def _root_relationships_xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/'
            'package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/package/2006/'
            'relationships/metadata/core-properties" '
            'Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" '
            'Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/extended-properties" '
            'Target="docProps/app.xml"/>'
            "</Relationships>"
        )

    def _workbook_xml(
        self,
        sheets: tuple[ExcelSheet, ...],
    ) -> str:
        sheet_entries = "".join(
            (
                f'<sheet name="{escape(sheet.name)}" '
                f'sheetId="{index}" r:id="rId{index}"/>'
            )
            for index, sheet in enumerate(
                sheets,
                start=1,
            )
        )

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships">'
            '<bookViews><workbookView/></bookViews>'
            f"<sheets>{sheet_entries}</sheets>"
            '<calcPr calcId="191029"/>'
            "</workbook>"
        )

    def _workbook_relationships_xml(
        self,
        sheet_count: int,
    ) -> str:
        relationships = "".join(
            (
                f'<Relationship Id="rId{index}" '
                'Type="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{index}.xml"/>'
            )
            for index in range(1, sheet_count + 1)
        )

        styles_relationship_id = sheet_count + 1

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/'
            'package/2006/relationships">'
            f"{relationships}"
            f'<Relationship Id="rId{styles_relationship_id}" '
            'Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
            "</Relationships>"
        )

    def _styles_xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main">'
            '<fonts count="3">'
            '<font><sz val="11"/><name val="Calibri"/></font>'
            '<font><b/><sz val="16"/><color rgb="FFFFFFFF"/>'
            '<name val="Calibri"/></font>'
            '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/>'
            '<name val="Calibri"/></font>'
            '</fonts>'
            '<fills count="4">'
            '<fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid">'
            '<fgColor rgb="FF0F766E"/><bgColor indexed="64"/>'
            '</patternFill></fill>'
            '<fill><patternFill patternType="solid">'
            '<fgColor rgb="FF334155"/><bgColor indexed="64"/>'
            '</patternFill></fill>'
            '</fills>'
            '<borders count="2">'
            '<border><left/><right/><top/><bottom/><diagonal/></border>'
            '<border>'
            '<left style="thin"><color rgb="FFD1D5DB"/></left>'
            '<right style="thin"><color rgb="FFD1D5DB"/></right>'
            '<top style="thin"><color rgb="FFD1D5DB"/></top>'
            '<bottom style="thin"><color rgb="FFD1D5DB"/></bottom>'
            '<diagonal/>'
            '</border>'
            '</borders>'
            '<cellStyleXfs count="1">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
            '</cellStyleXfs>'
            '<cellXfs count="4">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" '
            'xfId="0" applyBorder="1" applyAlignment="1">'
            '<alignment vertical="top" wrapText="1"/>'
            '</xf>'
            '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" '
            'xfId="0" applyFont="1" applyFill="1" '
            'applyAlignment="1">'
            '<alignment horizontal="left" vertical="center"/>'
            '</xf>'
            '<xf numFmtId="0" fontId="2" fillId="3" borderId="1" '
            'xfId="0" applyFont="1" applyFill="1" '
            'applyBorder="1" applyAlignment="1">'
            '<alignment horizontal="center" vertical="center"/>'
            '</xf>'
            '<xf numFmtId="4" fontId="0" fillId="0" borderId="1" '
            'xfId="0" applyNumberFormat="1" applyBorder="1" '
            'applyAlignment="1">'
            '<alignment vertical="top"/>'
            '</xf>'
            '</cellXfs>'
            '<cellStyles count="1">'
            '<cellStyle name="Normal" xfId="0" builtinId="0"/>'
            '</cellStyles>'
            '<dxfs count="0"/>'
            '<tableStyles count="0" defaultTableStyle="TableStyleMedium2" '
            'defaultPivotStyle="PivotStyleLight16"/>'
            '</styleSheet>'
        )

    def _core_properties_xml(self) -> str:
        generated_at = datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/'
            '2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>RADAR_SERVICE Observability Export</dc:title>'
            '<dc:creator>Pipeline Metrics Exporter</dc:creator>'
            '<cp:lastModifiedBy>Pipeline Metrics Exporter</cp:lastModifiedBy>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">'
            f"{generated_at}"
            '</dcterms:created>'
            '<dcterms:modified xsi:type="dcterms:W3CDTF">'
            f"{generated_at}"
            '</dcterms:modified>'
            '</cp:coreProperties>'
        )

    def _app_properties_xml(
        self,
        sheets: tuple[ExcelSheet, ...],
    ) -> str:
        titles = "".join(
            f"<vt:lpstr>{escape(sheet.name)}</vt:lpstr>"
            for sheet in sheets
        )

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/'
            'officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/'
            'officeDocument/2006/docPropsVTypes">'
            '<Application>Pipeline Metrics Exporter</Application>'
            '<DocSecurity>0</DocSecurity>'
            '<ScaleCrop>false</ScaleCrop>'
            '<HeadingPairs>'
            '<vt:vector size="2" baseType="variant">'
            '<vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>'
            f'<vt:variant><vt:i4>{len(sheets)}</vt:i4></vt:variant>'
            '</vt:vector>'
            '</HeadingPairs>'
            '<TitlesOfParts>'
            f'<vt:vector size="{len(sheets)}" baseType="lpstr">'
            f"{titles}"
            '</vt:vector>'
            '</TitlesOfParts>'
            '<Company>RADAR_SERVICE</Company>'
            '<LinksUpToDate>false</LinksUpToDate>'
            '<SharedDoc>false</SharedDoc>'
            '<HyperlinksChanged>false</HyperlinksChanged>'
            '<AppVersion>0.1.0</AppVersion>'
            '</Properties>'
        )


__all__ = [
    "EXCEL_COLUMNS",
    "EXCEL_CONTENT_TYPE",
    "ExcelExportError",
    "ExcelExportFileExistsError",
    "ExcelExporter",
    "ExcelSheet",
]
